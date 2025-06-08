# DataPreparationProcessor.py - Updated for modular Step 7
import pandas as pd
import numpy as np
import os
from shapely.geometry import Polygon, Point, MultiPolygon

# Import display_dataframe from utility_functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processors.utility_functions import display_dataframe

class DataPreparationProcessor:
    def __init__(self):
        self.cut_pieces_summary = None
        self.has_pattern = None
        self.tile_width = None
        self.tile_height = None
        self.half_threshold = None
    
    def create_cut_pieces_summary(self, tiles_df, has_pattern, tile_width, tile_height):
        """Create cut pieces summary for matching process"""
        print("\n📊 Creating cut pieces summary from tile data...")
        
        # Store parameters for later use
        self.has_pattern = has_pattern
        self.tile_width = tile_width
        self.tile_height = tile_height
        
        # Calculate half-tile threshold
        self.half_threshold = min(tile_width, tile_height) / 2
        
        if has_pattern:
            # Process X-direction cuts
            cut_x_tiles = tiles_df[tiles_df['classification'] == 'cut_x'].copy()
            x_less_than_half = []
            x_more_than_half = []
            
            for _, tile in cut_x_tiles.iterrows():
                cut_size = tile['cut_side']
                remaining_size = tile_width - cut_size
                
                summary = {
                    'Apartment': tile['apartment_name'],
                    'Location': tile['room_name'],
                    'Cut Size (mm)': round(cut_size, 1),
                    'Remaining Size (mm)': round(remaining_size, 1),
                    'Count': 1
                }
                
                if cut_size < self.half_threshold:
                    x_less_than_half.append(summary)
                else:
                    x_more_than_half.append(summary)
            
            # Process Y-direction cuts
            cut_y_tiles = tiles_df[tiles_df['classification'] == 'cut_y'].copy()
            y_less_than_half = []
            y_more_than_half = []
            
            for _, tile in cut_y_tiles.iterrows():
                cut_size = tile['cut_side']
                remaining_size = tile_height - cut_size
                
                summary = {
                    'Apartment': tile['apartment_name'],
                    'Location': tile['room_name'],
                    'Cut Size (mm)': round(cut_size, 1),
                    'Remaining Size (mm)': round(remaining_size, 1),
                    'Count': 1
                }
                
                if cut_size < self.half_threshold:
                    y_less_than_half.append(summary)
                else:
                    y_more_than_half.append(summary)
            
            # Convert to DataFrames and aggregate
            def aggregate_summary(summary_list):
                if not summary_list:
                    return pd.DataFrame()
                df = pd.DataFrame(summary_list)
                return df.groupby(['Apartment', 'Location', 'Cut Size (mm)', 'Remaining Size (mm)']).sum().reset_index()
            
            x_less_than_half_df = aggregate_summary(x_less_than_half)
            x_more_than_half_df = aggregate_summary(x_more_than_half)
            y_less_than_half_df = aggregate_summary(y_less_than_half)
            y_more_than_half_df = aggregate_summary(y_more_than_half)
            
            self.cut_pieces_summary = {
                'x_less_than_half': x_less_than_half_df,
                'x_more_than_half': x_more_than_half_df,
                'y_less_than_half': y_less_than_half_df,
                'y_more_than_half': y_more_than_half_df,
                'has_pattern': True,
                'tile_width': tile_width,
                'tile_height': tile_height,
                'half_threshold': self.half_threshold
            }
            
        else:
            # Process all cuts (no pattern)
            all_cut_tiles = tiles_df[tiles_df['classification'] == 'all_cut'].copy()
            all_less_than_half = []
            all_more_than_half = []
            
            for _, tile in all_cut_tiles.iterrows():
                cut_size = tile['cut_side']
                # For no pattern, use minimum dimension for remaining size calculation
                min_dimension = min(tile_width, tile_height)
                remaining_size = min_dimension - cut_size
                
                summary = {
                    'Apartment': tile['apartment_name'],
                    'Location': tile['room_name'],
                    'Cut Size (mm)': round(cut_size, 1),
                    'Remaining Size (mm)': round(remaining_size, 1),
                    'Count': 1
                }
                
                if cut_size < self.half_threshold:
                    all_less_than_half.append(summary)
                else:
                    all_more_than_half.append(summary)
            
            # Convert to DataFrames and aggregate
            def aggregate_summary(summary_list):
                if not summary_list:
                    return pd.DataFrame()
                df = pd.DataFrame(summary_list)
                return df.groupby(['Apartment', 'Location', 'Cut Size (mm)', 'Remaining Size (mm)']).sum().reset_index()
            
            all_less_than_half_df = aggregate_summary(all_less_than_half)
            all_more_than_half_df = aggregate_summary(all_more_than_half)
            
            self.cut_pieces_summary = {
                'all_less_than_half': all_less_than_half_df,
                'all_more_than_half': all_more_than_half_df,
                'has_pattern': False,
                'tile_width': tile_width,
                'tile_height': tile_height,
                'half_threshold': self.half_threshold
            }
        
        return self.cut_pieces_summary
    
    def display_cut_pieces_summary(self, cut_pieces_summary=None):
        """Display cut pieces summary in a formatted way"""
        if cut_pieces_summary is None:
            cut_pieces_summary = self.cut_pieces_summary
            
        if cut_pieces_summary is None:
            print("❌ No cut pieces summary available")
            return
            
        print("\n" + "="*50)
        print("📊 CUT PIECES SUMMARY")
        print("="*50)
        
        has_pattern = cut_pieces_summary['has_pattern']
        
        if has_pattern:
            # X Direction Summary
            print("\n🔹 X DIRECTION CUTS:")
            print("-"*30)
            x_less = cut_pieces_summary['x_less_than_half']
            x_more = cut_pieces_summary['x_more_than_half']
            
            if not x_less.empty:
                print(f"Less than half ({len(x_less)} types, {x_less['Count'].sum()} pieces):")
                display_dataframe(x_less.head(5), "X Less Than Half (Top 5)")
            else:
                print("Less than half: None")
            
            if not x_more.empty:
                print(f"\nMore than half ({len(x_more)} types, {x_more['Count'].sum()} pieces):")
                display_dataframe(x_more.head(5), "X More Than Half (Top 5)")
            else:
                print("\nMore than half: None")
            
            # Y Direction Summary
            print("\n🔹 Y DIRECTION CUTS:")
            print("-"*30)
            y_less = cut_pieces_summary['y_less_than_half']
            y_more = cut_pieces_summary['y_more_than_half']
            
            if not y_less.empty:
                print(f"Less than half ({len(y_less)} types, {y_less['Count'].sum()} pieces):")
                display_dataframe(y_less.head(5), "Y Less Than Half (Top 5)")
            else:
                print("Less than half: None")
            
            if not y_more.empty:
                print(f"\nMore than half ({len(y_more)} types, {y_more['Count'].sum()} pieces):")
                display_dataframe(y_more.head(5), "Y More Than Half (Top 5)")
            else:
                print("\nMore than half: None")
            
            # Inventory Summary if available
            if 'x_inv_less_than_half' in cut_pieces_summary:
                print("\n🔹 INVENTORY PIECES:")
                print("-"*30)
                
                x_inv_less = cut_pieces_summary.get('x_inv_less_than_half', pd.DataFrame())
                x_inv_more = cut_pieces_summary.get('x_inv_more_than_half', pd.DataFrame())
                y_inv_less = cut_pieces_summary.get('y_inv_less_than_half', pd.DataFrame())
                y_inv_more = cut_pieces_summary.get('y_inv_more_than_half', pd.DataFrame())
                
                x_inv_less_count = x_inv_less['Count'].sum() if not x_inv_less.empty else 0
                x_inv_more_count = x_inv_more['Count'].sum() if not x_inv_more.empty else 0
                y_inv_less_count = y_inv_less['Count'].sum() if not y_inv_less.empty else 0
                y_inv_more_count = y_inv_more['Count'].sum() if not y_inv_more.empty else 0
                
                print(f"X Inventory - Less: {len(x_inv_less)} types ({x_inv_less_count} pieces), More: {len(x_inv_more)} types ({x_inv_more_count} pieces)")
                print(f"Y Inventory - Less: {len(y_inv_less)} types ({y_inv_less_count} pieces), More: {len(y_inv_more)} types ({y_inv_more_count} pieces)")
                
        else:
            # All Cuts Summary
            print("\n🔹 ALL CUTS (NO PATTERN):")
            print("-"*30)
            all_less = cut_pieces_summary['all_less_than_half']
            all_more = cut_pieces_summary['all_more_than_half']
            
            if not all_less.empty:
                print(f"Less than half ({len(all_less)} types, {all_less['Count'].sum()} pieces):")
                display_dataframe(all_less.head(5), "All Less Than Half (Top 5)")
            else:
                print("Less than half: None")
            
            if not all_more.empty:
                print(f"\nMore than half ({len(all_more)} types, {all_more['Count'].sum()} pieces):")
                display_dataframe(all_more.head(5), "All More Than Half (Top 5)")
            else:
                print("\nMore than half: None")
            
            # Inventory Summary if available
            if 'all_inv_less_than_half' in cut_pieces_summary:
                print("\n🔹 INVENTORY PIECES:")
                print("-"*30)
                
                all_inv_less = cut_pieces_summary.get('all_inv_less_than_half', pd.DataFrame())
                all_inv_more = cut_pieces_summary.get('all_inv_more_than_half', pd.DataFrame())
                
                all_inv_less_count = all_inv_less['Count'].sum() if not all_inv_less.empty else 0
                all_inv_more_count = all_inv_more['Count'].sum() if not all_inv_more.empty else 0
                
                print(f"All Inventory - Less: {len(all_inv_less)} types ({all_inv_less_count} pieces), More: {len(all_inv_more)} types ({all_inv_more_count} pieces)")
    
    def create_inventory_template(self, template_filename=None):
        """Create Excel template for inventory input"""
        print("\n📋 Creating inventory template...")
        
        if self.has_pattern is None:
            print("❌ No pattern information available. Run create_cut_pieces_summary first.")
            return None
            
        if template_filename is None:
            if self.has_pattern:
                template_filename = 'inventory_template_pattern.xlsx'
            else:
                template_filename = 'inventory_template_no_pattern.xlsx'
        
        if self.has_pattern:
            # Create template for pattern mode (X and Y sheets)
            print("✅ Creating pattern-based inventory template (X and Y sheets)...")
            
            with pd.ExcelWriter(template_filename, engine='openpyxl') as writer:
                # X Direction template
                x_template = pd.DataFrame({
                    'Apartment': ['A101', 'A101', 'A102'],
                    'Location': ['Living', 'Bedroom', 'Kitchen'],
                    'Cut Size (mm)': [150, 200, 100],
                    'Remaining Size (mm)': [450, 400, 500],
                    'Count': [2, 3, 1]
                })
                x_template.to_excel(writer, sheet_name='Inventory_X', index=False)
                
                # Y Direction template
                y_template = pd.DataFrame({
                    'Apartment': ['A101', 'A102', 'A102'],
                    'Location': ['Living', 'Bedroom', 'Bathroom'],
                    'Cut Size (mm)': [180, 250, 120],
                    'Remaining Size (mm)': [420, 350, 480],
                    'Count': [1, 2, 3]
                })
                y_template.to_excel(writer, sheet_name='Inventory_Y', index=False)
                
        else:
            # Create template for no pattern mode (single sheet)
            print("✅ Creating no-pattern inventory template (single sheet)...")
            
            with pd.ExcelWriter(template_filename, engine='openpyxl') as writer:
                all_template = pd.DataFrame({
                    'Apartment': ['A101', 'A101', 'A102', 'A102'],
                    'Location': ['Living', 'Bedroom', 'Kitchen', 'Bathroom'],
                    'Cut Size (mm)': [150, 200, 100, 250],
                    'Remaining Size (mm)': [450, 400, 500, 350],
                    'Count': [2, 3, 1, 2]
                })
                all_template.to_excel(writer, sheet_name='Inventory_All', index=False)
        
        print(f"✅ Created template: {template_filename}")
        
        # Display instructions
        self.display_inventory_instructions()
        
        return template_filename
    
    def display_inventory_instructions(self):
        """Display instructions for filling inventory template"""
        print("\n" + "-"*50)
        print("📝 INVENTORY TEMPLATE INSTRUCTIONS:")
        print("-"*50)
        print("1. Fill in the template with your inventory data:")
        print("   - Apartment: Must match your apartment names exactly")
        print("   - Location: Room name (e.g., Living, Kitchen, Bedroom)")
        print("   - Cut Size: The size of the cut piece in mm")
        print("   - Remaining Size: The remaining piece size in mm")
        print("   - Count: Number of pieces of this type")
        
        if self.tile_width and self.tile_height:
            print(f"\n2. IMPORTANT: Cut + Remaining should equal tile dimension:")
            if self.has_pattern:
                print(f"   - For X cuts (Inventory_X sheet): Cut + Remaining = {self.tile_width}mm")
                print(f"   - For Y cuts (Inventory_Y sheet): Cut + Remaining = {self.tile_height}mm")
            else:
                print(f"   - Cut + Remaining = {self.tile_width}mm or {self.tile_height}mm")
        
        print("\n3. Save the file and upload when prompted")
    
    def read_inventory_file(self, filepath=None, has_pattern=None):
        """Read inventory data from uploaded Excel file"""
        if has_pattern is None:
            has_pattern = self.has_pattern
            
        if not filepath:
            print("❌ No file path provided")
            return None
        
        try:
            print(f"✅ Reading inventory file: {filepath}")
            
            inventory_data = {}
            
            if has_pattern:
                # Read X and Y sheets
                try:
                    inventory_data['x'] = pd.read_excel(filepath, sheet_name='Inventory_X')
                    print(f"   ✅ Read Inventory_X: {len(inventory_data['x'])} rows")
                except Exception as e:
                    print(f"   ⚠️ Could not read Inventory_X sheet: {e}")
                    inventory_data['x'] = pd.DataFrame()
                
                try:
                    inventory_data['y'] = pd.read_excel(filepath, sheet_name='Inventory_Y')
                    print(f"   ✅ Read Inventory_Y: {len(inventory_data['y'])} rows")
                except Exception as e:
                    print(f"   ⚠️ Could not read Inventory_Y sheet: {e}")
                    inventory_data['y'] = pd.DataFrame()
                
            else:
                # Read single sheet for no pattern
                try:
                    inventory_data['all'] = pd.read_excel(filepath, sheet_name='Inventory_All')
                    print(f"   ✅ Read Inventory_All: {len(inventory_data['all'])} rows")
                except Exception as e:
                    print(f"   ⚠️ Could not read Inventory_All sheet: {e}")
                    inventory_data['all'] = pd.DataFrame()
            
            return inventory_data
            
        except Exception as e:
            print(f"❌ Error reading inventory file: {e}")
            return None
    
    def validate_inventory_data(self, inventory_data, tile_width=None, tile_height=None, has_pattern=None):
        """Validate inventory data for consistency"""
        if tile_width is None:
            tile_width = self.tile_width
        if tile_height is None:
            tile_height = self.tile_height
        if has_pattern is None:
            has_pattern = self.has_pattern
            
        print("\n🔍 Validating inventory data...")
        
        issues = []
        
        if has_pattern:
            # Validate X inventory
            if 'x' in inventory_data and not inventory_data['x'].empty:
                x_inv = inventory_data['x']
                for idx, row in x_inv.iterrows():
                    total = row['Cut Size (mm)'] + row['Remaining Size (mm)']
                    if abs(total - tile_width) > 1:  # 1mm tolerance
                        issues.append(f"Row {idx+1} in Inventory_X: Cut + Remaining = {total}, expected {tile_width}")
            
            # Validate Y inventory
            if 'y' in inventory_data and not inventory_data['y'].empty:
                y_inv = inventory_data['y']
                for idx, row in y_inv.iterrows():
                    total = row['Cut Size (mm)'] + row['Remaining Size (mm)']
                    if abs(total - tile_height) > 1:  # 1mm tolerance
                        issues.append(f"Row {idx+1} in Inventory_Y: Cut + Remaining = {total}, expected {tile_height}")
        
        else:
            # Validate all inventory
            if 'all' in inventory_data and not inventory_data['all'].empty:
                all_inv = inventory_data['all']
                for idx, row in all_inv.iterrows():
                    total = row['Cut Size (mm)'] + row['Remaining Size (mm)']
                    # For no pattern, accept both dimensions
                    if abs(total - tile_width) > 1 and abs(total - tile_height) > 1:
                        issues.append(f"Row {idx+1} in Inventory_All: Cut + Remaining = {total}, expected {tile_width} or {tile_height}")
        
        if issues:
            print("⚠️ Validation issues found:")
            for issue in issues[:5]:  # Show first 5 issues
                print(f"   - {issue}")
            if len(issues) > 5:
                print(f"   ... and {len(issues) - 5} more issues")
            
            proceed = input("\nProceed anyway? (y/n): ").strip().lower()
            if proceed != 'y':
                return False
        else:
            print("✅ Inventory data validation passed")
        
        return True
    
    def merge_inventory_with_cuts(self, cut_pieces_summary=None, inventory_data=None):
        """Merge inventory data with cut pieces summary"""
        if cut_pieces_summary is None:
            cut_pieces_summary = self.cut_pieces_summary
            
        print("\n🔄 Merging inventory data...")
        
        has_pattern = cut_pieces_summary['has_pattern']
        half_threshold = cut_pieces_summary['half_threshold']
        
        if has_pattern:
            # Process X inventory
            if 'x' in inventory_data and not inventory_data['x'].empty:
                x_inv = inventory_data['x'].copy()
                x_inv_less = x_inv[x_inv['Remaining Size (mm)'] < half_threshold].copy()
                x_inv_more = x_inv[x_inv['Remaining Size (mm)'] >= half_threshold].copy()
                
                cut_pieces_summary['x_inv_less_than_half'] = x_inv_less
                cut_pieces_summary['x_inv_more_than_half'] = x_inv_more
                print(f"   ✅ X inventory: {len(x_inv_less)} less-than-half, {len(x_inv_more)} more-than-half")
            
            # Process Y inventory
            if 'y' in inventory_data and not inventory_data['y'].empty:
                y_inv = inventory_data['y'].copy()
                y_inv_less = y_inv[y_inv['Remaining Size (mm)'] < half_threshold].copy()
                y_inv_more = y_inv[y_inv['Remaining Size (mm)'] >= half_threshold].copy()
                
                cut_pieces_summary['y_inv_less_than_half'] = y_inv_less
                cut_pieces_summary['y_inv_more_than_half'] = y_inv_more
                print(f"   ✅ Y inventory: {len(y_inv_less)} less-than-half, {len(y_inv_more)} more-than-half")
            
        else:
            # Process all inventory
            if 'all' in inventory_data and not inventory_data['all'].empty:
                all_inv = inventory_data['all'].copy()
                all_inv_less = all_inv[all_inv['Remaining Size (mm)'] < half_threshold].copy()
                all_inv_more = all_inv[all_inv['Remaining Size (mm)'] >= half_threshold].copy()
                
                cut_pieces_summary['all_inv_less_than_half'] = all_inv_less
                cut_pieces_summary['all_inv_more_than_half'] = all_inv_more
                print(f"   ✅ All inventory: {len(all_inv_less)} less-than-half, {len(all_inv_more)} more-than-half")
        
        # Update the stored summary
        self.cut_pieces_summary = cut_pieces_summary
        
        return cut_pieces_summary
    
    def generate_inventory_from_more_than_half(self, cut_pieces_summary=None):
        """Generate inventory from more-than-half pieces"""
        if cut_pieces_summary is None:
            cut_pieces_summary = self.cut_pieces_summary
            
        print("\n📦 Generating inventory from more-than-half pieces...")
        
        has_pattern = cut_pieces_summary['has_pattern']
        half_threshold = cut_pieces_summary['half_threshold']
        
        if has_pattern:
            # Process X direction
            x_more = cut_pieces_summary.get('x_more_than_half', pd.DataFrame())
            if not x_more.empty:
                x_inv_summary = []
                for _, row in x_more.iterrows():
                    x_inv_summary.append({
                        'Apartment': 'INVENTORY',
                        'Location': f"{row['Apartment']}-{row['Location']}",
                        'Cut Size (mm)': row['Cut Size (mm)'],
                        'Remaining Size (mm)': row['Remaining Size (mm)'],
                        'Count': row['Count']
                    })
                x_inv_df = pd.DataFrame(x_inv_summary)
                
                x_inv_less = x_inv_df[x_inv_df['Remaining Size (mm)'] < half_threshold].copy()
                x_inv_more = x_inv_df[x_inv_df['Remaining Size (mm)'] >= half_threshold].copy()
                
                # Add to existing inventory
                if 'x_inv_less_than_half' in cut_pieces_summary and not cut_pieces_summary['x_inv_less_than_half'].empty:
                    cut_pieces_summary['x_inv_less_than_half'] = pd.concat([
                        cut_pieces_summary['x_inv_less_than_half'], x_inv_less
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['x_inv_less_than_half'] = x_inv_less
                
                if 'x_inv_more_than_half' in cut_pieces_summary and not cut_pieces_summary['x_inv_more_than_half'].empty:
                    cut_pieces_summary['x_inv_more_than_half'] = pd.concat([
                        cut_pieces_summary['x_inv_more_than_half'], x_inv_more
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['x_inv_more_than_half'] = x_inv_more
            
            # Process Y direction
            y_more = cut_pieces_summary.get('y_more_than_half', pd.DataFrame())
            if not y_more.empty:
                y_inv_summary = []
                for _, row in y_more.iterrows():
                    y_inv_summary.append({
                        'Apartment': 'INVENTORY',
                        'Location': f"{row['Apartment']}-{row['Location']}",
                        'Cut Size (mm)': row['Cut Size (mm)'],
                        'Remaining Size (mm)': row['Remaining Size (mm)'],
                        'Count': row['Count']
                    })
                y_inv_df = pd.DataFrame(y_inv_summary)
                
                y_inv_less = y_inv_df[y_inv_df['Remaining Size (mm)'] < half_threshold].copy()
                y_inv_more = y_inv_df[y_inv_df['Remaining Size (mm)'] >= half_threshold].copy()
                
                if 'y_inv_less_than_half' in cut_pieces_summary and not cut_pieces_summary['y_inv_less_than_half'].empty:
                    cut_pieces_summary['y_inv_less_than_half'] = pd.concat([
                        cut_pieces_summary['y_inv_less_than_half'], y_inv_less
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['y_inv_less_than_half'] = y_inv_less
                
                if 'y_inv_more_than_half' in cut_pieces_summary and not cut_pieces_summary['y_inv_more_than_half'].empty:
                    cut_pieces_summary['y_inv_more_than_half'] = pd.concat([
                        cut_pieces_summary['y_inv_more_than_half'], y_inv_more
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['y_inv_more_than_half'] = y_inv_more
                    
        else:
            # Process all cuts
            all_more = cut_pieces_summary.get('all_more_than_half', pd.DataFrame())
            if not all_more.empty:
                all_inv_summary = []
                for _, row in all_more.iterrows():
                    all_inv_summary.append({
                        'Apartment': 'INVENTORY',
                        'Location': f"{row['Apartment']}-{row['Location']}",
                        'Cut Size (mm)': row['Cut Size (mm)'],
                        'Remaining Size (mm)': row['Remaining Size (mm)'],
                        'Count': row['Count']
                    })
                all_inv_df = pd.DataFrame(all_inv_summary)
                
                all_inv_less = all_inv_df[all_inv_df['Remaining Size (mm)'] < half_threshold].copy()
                all_inv_more = all_inv_df[all_inv_df['Remaining Size (mm)'] >= half_threshold].copy()
                
                if 'all_inv_less_than_half' in cut_pieces_summary and not cut_pieces_summary['all_inv_less_than_half'].empty:
                    cut_pieces_summary['all_inv_less_than_half'] = pd.concat([
                        cut_pieces_summary['all_inv_less_than_half'], all_inv_less
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['all_inv_less_than_half'] = all_inv_less
                
                if 'all_inv_more_than_half' in cut_pieces_summary and not cut_pieces_summary['all_inv_more_than_half'].empty:
                    cut_pieces_summary['all_inv_more_than_half'] = pd.concat([
                        cut_pieces_summary['all_inv_more_than_half'], all_inv_more
                    ]).reset_index(drop=True)
                else:
                    cut_pieces_summary['all_inv_more_than_half'] = all_inv_more
        
        print("✅ Generated inventory from more-than-half pieces")
        
        # Update the stored summary
        self.cut_pieces_summary = cut_pieces_summary
        
        return cut_pieces_summary
    
    def get_summary_statistics(self, cut_pieces_summary=None):
        """Get summary statistics for the cut pieces"""
        if cut_pieces_summary is None:
            cut_pieces_summary = self.cut_pieces_summary
            
        stats = {
            'apartment_pieces': 0,
            'inventory_pieces': 0,
            'total_pieces': 0
        }
        
        if cut_pieces_summary['has_pattern']:
            # Count apartment pieces
            for key in ['x_less_than_half', 'x_more_than_half', 'y_less_than_half', 'y_more_than_half']:
                df = cut_pieces_summary.get(key, pd.DataFrame())
                if not df.empty:
                    stats['apartment_pieces'] += df['Count'].sum()
            
            # Count inventory pieces
            for key in ['x_inv_less_than_half', 'x_inv_more_than_half', 'y_inv_less_than_half', 'y_inv_more_than_half']:
                df = cut_pieces_summary.get(key, pd.DataFrame())
                if not df.empty:
                    stats['inventory_pieces'] += df['Count'].sum()
        else:
            # Count apartment pieces
            for key in ['all_less_than_half', 'all_more_than_half']:
                df = cut_pieces_summary.get(key, pd.DataFrame())
                if not df.empty:
                    stats['apartment_pieces'] += df['Count'].sum()
            
            # Count inventory pieces
            for key in ['all_inv_less_than_half', 'all_inv_more_than_half']:
                df = cut_pieces_summary.get(key, pd.DataFrame())
                if not df.empty:
                    stats['inventory_pieces'] += df['Count'].sum()
        
        stats['total_pieces'] = stats['apartment_pieces'] + stats['inventory_pieces']
        
        return stats