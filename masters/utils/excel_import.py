# masters/utils/excel_import.py

import pandas as pd
import numpy as np
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
import uuid
import logging
from masters.models import Group2, Grade, Item

logger = logging.getLogger(__name__)

class ItemMasterImporter:
    """
    Utility to import Item Master from Excel file
    Expected Excel columns: Group2, Grade, Item Code, Description, Unit Weight, etc.
    """
    
    def __init__(self, excel_file):
        self.excel_file = excel_file
        self.stats = {
            'total_rows': 0,
            'group2_created': 0,
            'group2_updated': 0,
            'grades_created': 0,
            'grades_updated': 0,
            'items_created': 0,
            'items_updated': 0,
            'errors': []
        }
        self.import_batch_id = str(uuid.uuid4())[:8]
    
    def import_data(self):
        """Main import function"""
        try:
            # Read Excel file
            df = pd.read_excel(self.excel_file)
            self.stats['total_rows'] = len(df)
            
            # Clean and prepare data
            df = self._clean_dataframe(df)
            
            # Process with transaction
            with transaction.atomic():
                self._process_hierarchy(df)
            
            return {
                'success': True,
                'stats': self.stats,
                'import_batch_id': self.import_batch_id
            }
            
        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }
    
    def _clean_dataframe(self, df):
        """Clean and standardize dataframe"""
        # Standardize column names (handle variations)
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        # Map common column names
        column_mapping = {}
        for col in df.columns:
            if col in ['group2', 'group_2', 'group']:
                column_mapping[col] = 'group2'
            elif col in ['grade', 'gr']:
                column_mapping[col] = 'grade'
            elif col in ['item_code', 'itemcode', 'code', 'item_master_id', 'item_id']:
                column_mapping[col] = 'item_code'
            elif col in ['description', 'desc', 'item_description']:
                column_mapping[col] = 'description'
            elif col in ['unit_weight', 'weight', 'wt']:
                column_mapping[col] = 'unit_weight'
            elif col in ['hsn', 'hsn_code']:
                column_mapping[col] = 'hsn_code'
            elif col in ['tax', 'tax_rate', 'gst']:
                column_mapping[col] = 'tax_rate'
        
        df = df.rename(columns=column_mapping)
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Fill NaN values
        df = df.fillna({
            'unit_weight': 0,
            'hsn_code': '',
            'tax_rate': 0,
            'description': ''
        })
        
        return df
    
    def _process_hierarchy(self, df):
        """Process Group2, Grade, and Item hierarchy"""
        
        # Process unique Group2 values
        unique_group2 = df['group2'].unique() if 'group2' in df.columns else []
        
        for group2_code in unique_group2:
            if pd.isna(group2_code) or not str(group2_code).strip():
                continue
                
            group2_code = str(group2_code).strip()
            
            # Get or create Group2
            group2, created = Group2.objects.update_or_create(
                code=group2_code,
                defaults={
                    'name': group2_code,
                    'description': f"Imported from Excel batch {self.import_batch_id}"
                }
            )
            
            if created:
                self.stats['group2_created'] += 1
            else:
                self.stats['group2_updated'] += 1
            
            # Process grades for this Group2
            group2_data = df[df['group2'] == group2_code]
            unique_grades = group2_data['grade'].unique() if 'grade' in group2_data.columns else []
            
            for grade_code in unique_grades:
                if pd.isna(grade_code) or not str(grade_code).strip():
                    continue
                    
                grade_code = str(grade_code).strip()
                
                # Get or create Grade
                grade, created = Grade.objects.update_or_create(
                    group2=group2,
                    code=grade_code,
                    defaults={
                        'name': grade_code,
                        'description': f"Imported from Excel batch {self.import_batch_id}"
                    }
                )
                
                if created:
                    self.stats['grades_created'] += 1
                else:
                    self.stats['grades_updated'] += 1
                
                # Process items for this grade
                grade_data = group2_data[group2_data['grade'] == grade_code]
                
                for _, row in grade_data.iterrows():
                    self._process_item(row, group2, grade)
    
    def _process_item(self, row, group2, grade):
        """Process individual item"""
        try:
            item_code = str(row.get('item_code', '')).strip()
            if not item_code:
                return
            
            # Prepare item data
            item_data = {
                'group2': group2,
                'grade': grade,
                'item_description': str(row.get('description', ''))[:500],
                'unit_weight': float(row.get('unit_weight', 0)),
                'hsn_code': str(row.get('hsn_code', ''))[:20],
                'tax_rate': float(row.get('tax_rate', 0)) if pd.notna(row.get('tax_rate')) else None,
                'is_active': True,
                'import_batch_id': self.import_batch_id
            }
            
            # Update or create item
            item, created = Item.objects.update_or_create(
                item_master_id=item_code,
                defaults=item_data
            )
            
            if created:
                self.stats['items_created'] += 1
            else:
                self.stats['items_updated'] += 1
                
        except Exception as e:
            error_msg = f"Error processing item {row.get('item_code', 'unknown')}: {str(e)}"
            self.stats['errors'].append(error_msg)
            logger.error(error_msg)