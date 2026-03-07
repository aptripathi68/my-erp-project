@staff_member_required
def bom_upload(request):
    context = {}

    # Step 1: upload file and detect headers
    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]
        bom_name = request.POST.get("bom_name") or f.name

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            for chunk in f.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        from .services.bom_importer import workbook_sheet_headers

        headers_info = workbook_sheet_headers(tmp_path)

        request.session["bom_tmp_path"] = tmp_path
        request.session["bom_name"] = bom_name

        context["bom_name"] = bom_name
        context["headers_info"] = headers_info
        context["mapping_step"] = True
        context["result"] = None
        return render(request, "procurement/bom_upload.html", context)

    # Step 2: validate or import using user mapping
    if request.method == "POST" and request.POST.get("action") in ["validate", "import"]:
        tmp_path = request.session.get("bom_tmp_path")
        bom_name = request.session.get("bom_name", "Uploaded BOM")

        if not tmp_path:
            context["error"] = "Please upload the BOM file first."
            return render(request, "procurement/bom_upload.html", context)

        from .services.bom_importer import workbook_sheet_headers

        headers_info = workbook_sheet_headers(tmp_path)

        user_sheet_mappings = {}

        for sheet_name, info in headers_info.items():
            if not info.get("detected"):
                continue

            user_sheet_mappings[sheet_name] = {
                "item_description": request.POST.get(f"{sheet_name}__item_description", ""),
                "grade": request.POST.get(f"{sheet_name}__grade", ""),
                "mark_no": request.POST.get(f"{sheet_name}__mark_no", ""),
                "drawing_no": request.POST.get(f"{sheet_name}__drawing_no", ""),
                "item_no": request.POST.get(f"{sheet_name}__item_no", ""),
                "qty_all": request.POST.get(f"{sheet_name}__qty_all", ""),
                "length": request.POST.get(f"{sheet_name}__length", ""),
                "width": request.POST.get(f"{sheet_name}__width", ""),
                "thk": request.POST.get(f"{sheet_name}__thk", ""),
                "unit_wt": request.POST.get(f"{sheet_name}__unit_wt", ""),
            }

        result = validate_and_extract_workbook(
            tmp_path,
            user_sheet_mappings=user_sheet_mappings,
        )

        request.session["bom_validation_errors"] = result.get("errors", [])

        context["result"] = result
        context["bom_name"] = bom_name
        context["headers_info"] = headers_info
        context["mapping_step"] = True

        if request.POST.get("action") == "import" and result["ok"]:
            with transaction.atomic():
                header = BOMHeader.objects.create(
                    bom_name=bom_name,
                    uploaded_by=request.user,
                    uploaded_at=timezone.now(),
                )

                mark_map = {}
                for row in result["extracted"]:
                    key = (row.sheet_name, row.mark_no or "")
                    if key not in mark_map:
                        mark_map[key] = BOMMark.objects.create(
                            bom=header,
                            sheet_name=row.sheet_name,
                            mark_no=row.mark_no or "",
                            drawing_no=row.drawing_no or "",
                        )

                comps = []
                for row in result["extracted"]:
                    m = mark_map[(row.sheet_name, row.mark_no or "")]
                    comps.append(
                        BOMComponent(
                            mark=m,
                            item_no=row.item_no or "",
                            item_id=row.item_id,
                            item_description_raw=row.item_description_raw,
                            qty_all=row.qty_all,
                            length_mm=row.length_mm,
                            line_weight_kg=row.line_weight_kg,
                            excel_row=row.excel_row,
                        )
                    )

                BOMComponent.objects.bulk_create(comps, batch_size=2000)

            context["imported_bom_id"] = header.id

        return render(request, "procurement/bom_upload.html", context)

    return render(request, "procurement/bom_upload.html", context)