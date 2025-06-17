import pandas as pd
import numpy as np
import re

class MatchingProcessor:
    def __init__(self):
        # Define colors - matching Colab exactly
        self.SAME_APT_COLORS = [
            '#FFD700', '#FFA500', '#FF6347', '#FF1493', '#9932CC', 
            '#4169E1', '#00BFFF', '#00FA9A', '#ADFF2F', '#FFD700'
        ]
        self.DIFF_APT_COLOR = '#A9A9A9'
        self.INV_COLOR = '#8FBC8F'
        self.UNMATCHED_COLOR = '#FFFFFF'
        self.FULL_TILE_COLOR = '#E6E6FA'
        self.IRREGULAR_COLOR = '#F0E68C'

    def expand_dataframe(self, df):
        """Expand DataFrame rows based on Count column"""
        expanded = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            count = int(row_dict.get('Count', 1))
            if 'Count' in row_dict:
                del row_dict['Count']
            for _ in range(count):
                expanded.append(row_dict.copy())
        return expanded

    def match_with_inventory(self, cut_pieces, inventory_pieces, tolerance_ranges, direction="X"):
        """Match cut pieces with inventory using progressive tolerance"""
        matches = []
        inv_counter = 1
        cut_copy = [item.copy() for item in cut_pieces]
        inv_copy = [item.copy() for item in inventory_pieces]
        
        for item in cut_copy:
            item['Matched'] = False
        for item in inv_copy:
            item['Matched'] = False

        for tolerance in tolerance_ranges:
            matches_in_range = 0
            for i, cut in enumerate(cut_copy):
                if cut['Matched']:
                    continue
                
                cut_size = cut['Cut Size (mm)']
                cut_apt = cut['Apartment']
                cut_loc = cut['Location']
                cut_remain = cut['Remaining Size (mm)']
                
                best_match_idx = None
                best_waste = float('inf')
                
                for j, inv in enumerate(inv_copy):
                    if inv['Matched']:
                        continue
                    
                    inv_size = inv['Remaining Size (mm)']
                    inv_loc = inv['Location']
                    
                    if inv_size >= cut_size:
                        waste = inv_size - cut_size
                        if waste <= tolerance and waste < best_waste:
                            best_waste = waste
                            best_match_idx = j
                
                if best_match_idx is not None:
                    inv = inv_copy[best_match_idx]
                    inv_size = inv['Remaining Size (mm)']
                    inv_loc = inv['Location']
                    
                    if direction == "X":
                        match_id = f"IX{inv_counter}"
                    elif direction == "Y":
                        match_id = f"IY{inv_counter}"
                    else:
                        match_id = f"I{inv_counter}"
                    
                    inv_counter += 1
                    
                    matches.append({
                        'Match ID': match_id,
                        'Apartment': cut_apt,
                        'Location': cut_loc,
                        'Cut Size (mm)': cut_size,
                        'Cut Remain (mm)': cut_remain,
                        'Inventory Location': inv_loc,
                        'Inventory Size (mm)': inv_size,
                        'Waste': waste,
                        'Tolerance Range': f"<={tolerance}mm"
                    })
                    
                    cut_copy[i]['Matched'] = True
                    inv_copy[best_match_idx]['Matched'] = True
                    matches_in_range += 1
            
            if matches_in_range > 0:
                print(f"      Found {matches_in_range} inventory matches in tolerance range <= {tolerance}mm")
        
        unmatched_cut = [item for item in cut_copy if not item['Matched']]
        unmatched_inv = [item for item in inv_copy if not item['Matched']]
        return matches, unmatched_cut, unmatched_inv

    def match_with_progressive_tolerance(self, less_pieces, more_pieces, tolerance_ranges, direction="X"):
        """Match pieces with progressive tolerance (apartment to apartment matching)"""
        matches = []
        same_apt_counter = 1
        diff_apt_counter = 1
        
        less_copy = [item.copy() for item in less_pieces]
        more_copy = [item.copy() for item in more_pieces]
        
        for item in less_copy:
            item['Matched'] = False
        for item in more_copy:
            item['Matched'] = False

        for tolerance in tolerance_ranges:
            matches_in_range = 0
            for i, less in enumerate(less_copy):
                if less['Matched']:
                    continue
                
                less_size = less['Cut Size (mm)']
                less_apt = less['Apartment']
                less_loc = less['Location']
                less_remain = less['Remaining Size (mm)']
                
                best_match_idx = None
                best_waste = float('inf')
                
                for j, more in enumerate(more_copy):
                    if more['Matched']:
                        continue
                    
                    more_size = more['Cut Size (mm)']
                    more_apt = more['Apartment']
                    more_loc = more['Location']
                    
                    if less_remain > more_size:
                        waste = less_remain - more_size
                        if waste <= tolerance and waste < best_waste:
                            best_waste = waste
                            best_match_idx = j
                
                if best_match_idx is not None:
                    more = more_copy[best_match_idx]
                    more_size = more['Cut Size (mm)']
                    more_apt = more['Apartment']
                    more_loc = more['Location']
                    
                    is_same_apt = less_apt == more_apt
                    
                    if direction == "X":
                        if is_same_apt:
                            match_id = f"X{same_apt_counter}"
                        else:
                            match_id = f"OX{diff_apt_counter}"
                    elif direction == "Y":
                        if is_same_apt:
                            match_id = f"Y{same_apt_counter}"
                        else:
                            match_id = f"OY{diff_apt_counter}"
                    else:
                        if is_same_apt:
                            match_id = f"XY{same_apt_counter}"
                        else:
                            match_id = f"O{diff_apt_counter}"
                    
                    if is_same_apt:
                        same_apt_counter += 1
                    else:
                        diff_apt_counter += 1
                    
                    matches.append({
                        'Match ID': match_id,
                        'Small Piece Apt': less_apt,
                        'Small Piece Loc': less_loc,
                        'Small Piece Size': less_size,
                        'Small Piece Remain': less_remain,
                        'Large Piece Apt': more_apt,
                        'Large Piece Loc': more_loc,
                        'Large Piece Size': more_size,
                        'Waste': waste,
                        'Tolerance Range': f"<={tolerance}mm",
                        'Same Apartment': is_same_apt
                    })
                    
                    less_copy[i]['Matched'] = True
                    more_copy[best_match_idx]['Matched'] = True
                    matches_in_range += 1
            
            if matches_in_range > 0:
                print(f"      Found {matches_in_range} apartment matches in tolerance range <= {tolerance}mm")
        
        unmatched_less = [item for item in less_copy if not item['Matched']]
        unmatched_more = [item for item in more_copy if not item['Matched']]
        return matches, unmatched_less, unmatched_more

    def create_apartment_report(self, apt_match_df, inv_match_df, less_df, more_df, 
                              cut_pieces_by_half, direction="X"):
        """Create comprehensive apartment report with colors"""
        if less_df.empty and more_df.empty:
            return None
        
        # Define prefixes
        if direction == "X":
            same_apt_prefix = "X"
            diff_apt_prefix = "OX"
            inv_prefix = "IX"
        elif direction == "Y":
            same_apt_prefix = "Y"
            diff_apt_prefix = "OY"
            inv_prefix = "IY"
        else:
            same_apt_prefix = "XY"
            diff_apt_prefix = "O"
            inv_prefix = "I"
        
        # Create match mapping
        match_map = {}
        
        # Process apartment matches
        if not apt_match_df.empty:
            for _, match in apt_match_df.iterrows():
                small_apt = match['Small Piece Apt']
                small_loc = match['Small Piece Loc']
                small_size = round(match['Small Piece Size'], 1)
                large_apt = match['Large Piece Apt']
                large_loc = match['Large Piece Loc']
                large_size = round(match['Large Piece Size'], 1)
                match_id = match['Match ID']
                same_apartment = match['Same Apartment']
                
                # Determine color
                if same_apartment:
                    match_num = int(re.search(r'\d+', match_id).group())
                    color_idx = (match_num - 1) % len(self.SAME_APT_COLORS)
                    color = self.SAME_APT_COLORS[color_idx]
                else:
                    color = self.DIFF_APT_COLOR
                
                # Create keys
                small_key = (small_apt, small_loc, small_size, 'Less than Half')
                large_key = (large_apt, large_loc, large_size, 'More than Half')
                
                # Add to match map
                for key in [small_key, large_key]:
                    if key not in match_map:
                        match_map[key] = {'match_ids': [], 'colors': [], 'partners': [], 'same_apt': []}
                    match_map[key]['match_ids'].append(match_id)
                    match_map[key]['colors'].append(color)
                    match_map[key]['same_apt'].append(same_apartment)
                    
                    if key == small_key:
                        match_map[key]['partners'].append((large_apt, large_loc, large_size))
                    else:
                        match_map[key]['partners'].append((small_apt, small_loc, small_size))
        
        # Process inventory matches for remarks
        inv_matches_by_apt = {}
        if not inv_match_df.empty:
            for _, match in inv_match_df.iterrows():
                apt = match['Apartment']
                loc = match['Location']
                cut_size = round(match['Cut Size (mm)'], 1)
                inv_loc = match['Inventory Location']
                inv_size = round(match['Inventory Size (mm)'], 1)
                match_id = match['Match ID']
                
                apt_key = (apt, loc, cut_size, 'Less than Half')
                if apt_key not in inv_matches_by_apt:
                    inv_matches_by_apt[apt_key] = []
                inv_matches_by_apt[apt_key].append((match_id, inv_loc, inv_size))
        
        # Get original pieces data
        has_pattern = cut_pieces_by_half['has_pattern']
        if has_pattern and direction == "X":
            original_less = cut_pieces_by_half['x_less_than_half'].copy()
            original_more = cut_pieces_by_half['x_more_than_half'].copy()
        elif has_pattern and direction == "Y":
            original_less = cut_pieces_by_half['y_less_than_half'].copy()
            original_more = cut_pieces_by_half['y_more_than_half'].copy()
        else:
            original_less = cut_pieces_by_half['all_less_than_half'].copy()
            original_more = cut_pieces_by_half['all_more_than_half'].copy()
        
        apartment_pieces = []
        
        # Process less than half pieces
        for _, row in original_less.iterrows():
            apt = row['Apartment']
            loc = row['Location']
            cut_size = round(row['Cut Size (mm)'], 1)
            remain_size = round(row['Remaining Size (mm)'], 1)
            count = int(row['Count'])
            
            key = (apt, loc, cut_size, 'Less than Half')
            
            # Check for apartment matches
            apt_matches = match_map.get(key, {})
            apt_match_ids = apt_matches.get('match_ids', [])
            apt_colors = apt_matches.get('colors', [])
            apt_partners = apt_matches.get('partners', [])
            apt_same_apt = apt_matches.get('same_apt', [])
            
            # Check for inventory matches
            inv_matches = inv_matches_by_apt.get(key, [])
            
            # Create entries for apartment matches
            if apt_match_ids:
                partner_groups = {}
                for i, partner in enumerate(apt_partners):
                    if partner not in partner_groups:
                        partner_groups[partner] = {'ids': [], 'colors': [], 'same_apt': []}
                    if i < len(apt_match_ids):
                        partner_groups[partner]['ids'].append(apt_match_ids[i])
                    if i < len(apt_colors):
                        partner_groups[partner]['colors'].append(apt_colors[i])
                    if i < len(apt_same_apt):
                        partner_groups[partner]['same_apt'].append(apt_same_apt[i])
                
                for partner, info in partner_groups.items():
                    match_ids = info['ids']
                    color = info['colors'][0] if info['colors'] else ""
                    is_same_apt = info['same_apt'][0] if info['same_apt'] else False
                    
                    partner_apt, partner_loc, _ = partner
                    match_ids_str = ', '.join(match_ids)
                    
                    if len(match_ids) > 1:
                        remarks = f"{len(match_ids)} Matches ({match_ids_str}) with {partner_apt}-{partner_loc} ({'same' if is_same_apt else 'different'} apartment)"
                    else:
                        remarks = f"Match {match_ids_str} with {partner_apt}-{partner_loc} ({'same' if is_same_apt else 'different'} apartment)"
                    
                    # Add inventory match information to remarks
                    if inv_matches:
                        inv_locs = {}
                        for match_id, inv_loc, _ in inv_matches:
                            if inv_loc not in inv_locs:
                                inv_locs[inv_loc] = []
                            inv_locs[inv_loc].append(match_id)
                        
                        for inv_loc, inv_match_ids in inv_locs.items():
                            if len(inv_match_ids) > 1:
                                inv_remark = f"{len(inv_match_ids)} Inventory Matches ({', '.join(inv_match_ids)}) from {inv_loc}"
                            else:
                                inv_remark = f"Inventory Match {inv_match_ids[0]} from {inv_loc}"
                            remarks += "\n" + inv_remark
                    
                    apartment_pieces.append({
                        'Apartment': apt, 'Location': loc, 'Cut Size': cut_size,
                        'Remaining Size': remain_size, 'Count': len(match_ids),
                        'Group ID': match_ids[0], 'Color': color, 'Remarks': remarks,
                        'Piece Type': 'Less than Half', 'Match Type': 'Apartment'
                    })
                
                count -= len(apt_match_ids)
            
            # Create entries for inventory-only matches
            elif inv_matches:
                inv_locs = {}
                for match_id, inv_loc, _ in inv_matches:
                    if inv_loc not in inv_locs:
                        inv_locs[inv_loc] = []
                    inv_locs[inv_loc].append(match_id)
                
                for inv_loc, inv_match_ids in inv_locs.items():
                    if len(inv_match_ids) > 1:
                        inv_remarks = f"{len(inv_match_ids)} Inventory Matches ({', '.join(inv_match_ids)}) from {inv_loc}"
                    else:
                        inv_remarks = f"Inventory Match {inv_match_ids[0]} from {inv_loc}"
                    
                    apartment_pieces.append({
                        'Apartment': apt, 'Location': loc, 'Cut Size': cut_size,
                        'Remaining Size': remain_size, 'Count': len(inv_match_ids),
                        'Group ID': inv_match_ids[0], 'Color': self.INV_COLOR, 'Remarks': inv_remarks,
                        'Piece Type': 'Less than Half', 'Match Type': 'Inventory'
                    })
                
                count -= len(inv_matches)
            
            # Add unmatched pieces
            if count > 0:
                apartment_pieces.append({
                    'Apartment': apt, 'Location': loc, 'Cut Size': cut_size,
                    'Remaining Size': remain_size, 'Count': count,
                    'Group ID': '', 'Color': '', 'Remarks': f"{count} Unmatched piece(s)",
                    'Piece Type': 'Less than Half', 'Match Type': 'Unmatched'
                })
        
        # Process more than half pieces (similar logic)
        for _, row in original_more.iterrows():
            apt = row['Apartment']
            loc = row['Location']
            cut_size = round(row['Cut Size (mm)'], 1)
            remain_size = round(row['Remaining Size (mm)'], 1)
            count = int(row['Count'])
            
            key = (apt, loc, cut_size, 'More than Half')
            apt_matches = match_map.get(key, {})
            apt_match_ids = apt_matches.get('match_ids', [])
            apt_colors = apt_matches.get('colors', [])
            apt_partners = apt_matches.get('partners', [])
            apt_same_apt = apt_matches.get('same_apt', [])
            
            if apt_match_ids:
                partner_groups = {}
                for i, partner in enumerate(apt_partners):
                    if partner not in partner_groups:
                        partner_groups[partner] = {'ids': [], 'colors': [], 'same_apt': []}
                    if i < len(apt_match_ids):
                        partner_groups[partner]['ids'].append(apt_match_ids[i])
                    if i < len(apt_colors):
                        partner_groups[partner]['colors'].append(apt_colors[i])
                    if i < len(apt_same_apt):
                        partner_groups[partner]['same_apt'].append(apt_same_apt[i])
                
                for partner, info in partner_groups.items():
                    match_ids = info['ids']
                    color = info['colors'][0] if info['colors'] else ""
                    is_same_apt = info['same_apt'][0] if info['same_apt'] else False
                    
                    partner_apt, partner_loc, _ = partner
                    match_ids_str = ', '.join(match_ids)
                    
                    if len(match_ids) > 1:
                        remarks = f"{len(match_ids)} Matches ({match_ids_str}) with {partner_apt}-{partner_loc} ({'same' if is_same_apt else 'different'} apartment)"
                    else:
                        remarks = f"Match {match_ids_str} with {partner_apt}-{partner_loc} ({'same' if is_same_apt else 'different'} apartment)"
                    
                    apartment_pieces.append({
                        'Apartment': apt, 'Location': loc, 'Cut Size': cut_size,
                        'Remaining Size': remain_size, 'Count': len(match_ids),
                        'Group ID': match_ids[0], 'Color': color, 'Remarks': remarks,
                        'Piece Type': 'More than Half', 'Match Type': 'Apartment'
                    })
                
                count -= len(apt_match_ids)
            
            if count > 0:
                apartment_pieces.append({
                    'Apartment': apt, 'Location': loc, 'Cut Size': cut_size,
                    'Remaining Size': remain_size, 'Count': count,
                    'Group ID': '', 'Color': '', 'Remarks': f"{count} Unmatched piece(s)",
                    'Piece Type': 'More than Half', 'Match Type': 'Unmatched'
                })
        
        # Create DataFrame
        apartment_df = pd.DataFrame(apartment_pieces)
        if apartment_df.empty:
            return None
        
        # Rename Group IDs sequentially
        apartment_df['Group ID'] = self.create_sequential_group_ids(apartment_df, direction)
        apartment_df = apartment_df.sort_values(by=['Match Type', 'Apartment', 'Cut Size']).reset_index(drop=True)
        
        return apartment_df

    def create_sequential_group_ids(self, df, direction):
        """Create sequential group IDs for a dataframe"""
        same_apt_counter = 1
        diff_apt_counter = 1
        inv_counter = 1
        group_id_mapping = {}
        new_group_ids = []
        
        for _, row in df.iterrows():
            original_group_id = row['Group ID']
            match_type = row['Match Type']
            
            if original_group_id == '' or pd.isna(original_group_id):
                new_group_ids.append('')
                continue
            
            if original_group_id in group_id_mapping:
                new_group_ids.append(group_id_mapping[original_group_id])
                continue
            
            # Determine if it's a same apartment match
            is_same_apt = not (str(original_group_id).startswith('OX') or 
                             str(original_group_id).startswith('OY') or 
                             str(original_group_id).startswith('O'))
            
            if match_type == 'Apartment':
                if is_same_apt:
                    if direction == "X":
                        new_id = f"X{same_apt_counter}"
                    elif direction == "Y":
                        new_id = f"Y{same_apt_counter}"
                    else:
                        new_id = f"XY{same_apt_counter}"
                    same_apt_counter += 1
                else:
                    if direction == "X":
                        new_id = f"OX{diff_apt_counter}"
                    elif direction == "Y":
                        new_id = f"OY{diff_apt_counter}"
                    else:
                        new_id = f"O{diff_apt_counter}"
                    diff_apt_counter += 1
            elif match_type == 'Inventory':
                if direction == "X":
                    new_id = f"IX{inv_counter}"
                elif direction == "Y":
                    new_id = f"IY{inv_counter}"
                else:
                    new_id = f"I{inv_counter}"
                inv_counter += 1
            else:
                new_id = ''
            
            group_id_mapping[original_group_id] = new_id
            new_group_ids.append(new_id)
        
        return new_group_ids

    def create_inventory_report(self, inv_match_df, cut_pieces_by_half, direction="X"):
        """Create inventory report"""
        if direction == "X":
            inv_prefix = "IX"
            if 'x_inv_less_than_half' in cut_pieces_by_half and 'x_inv_more_than_half' in cut_pieces_by_half:
                inv_less = cut_pieces_by_half['x_inv_less_than_half'].copy()
                inv_more = cut_pieces_by_half['x_inv_more_than_half'].copy()
            else:
                return None
        elif direction == "Y":
            inv_prefix = "IY"
            if 'y_inv_less_than_half' in cut_pieces_by_half and 'y_inv_more_than_half' in cut_pieces_by_half:
                inv_less = cut_pieces_by_half['y_inv_less_than_half'].copy()
                inv_more = cut_pieces_by_half['y_inv_more_than_half'].copy()
            else:
                return None
        else:
            inv_prefix = "I"
            if 'all_inv_less_than_half' in cut_pieces_by_half and 'all_inv_more_than_half' in cut_pieces_by_half:
                inv_less = cut_pieces_by_half['all_inv_less_than_half'].copy()
                inv_more = cut_pieces_by_half['all_inv_more_than_half'].copy()
            else:
                return None
        
        if inv_less.empty and inv_more.empty:
            return None
        
        # Create mapping for renaming Group IDs
        inv_counter = 1
        match_id_to_group_id = {}
        
        if not inv_match_df.empty:
            for _, match in inv_match_df.iterrows():
                match_id = match['Match ID']
                if match_id not in match_id_to_group_id:
                    new_group_id = f"{inv_prefix}{inv_counter}"
                    inv_counter += 1
                    match_id_to_group_id[match_id] = new_group_id
        
        # Create inventory matches mapping
        inventory_matches = {}
        if not inv_match_df.empty:
            for _, match in inv_match_df.iterrows():
                inv_loc = match['Inventory Location']
                inv_size = round(match['Inventory Size (mm)'], 1)
                apt = match['Apartment']
                loc = match['Location']
                cut_size = round(match['Cut Size (mm)'], 1)
                waste = round(match['Waste'], 1)
                match_id = match['Match ID']
                group_id = match_id_to_group_id[match_id]
                
                key = (inv_loc, inv_size)
                if key not in inventory_matches:
                    inventory_matches[key] = []
                
                inventory_matches[key].append({
                    'match_id': match_id,
                    'group_id': group_id,
                    'apt': apt,
                    'loc': loc,
                    'cut_size': cut_size,
                    'waste': waste
                })
        
        # Create inventory report rows
        inventory_rows = []
        for df, piece_type in [(inv_less, 'Less than Half'), (inv_more, 'More than Half')]:
            if df.empty:
                continue
            
            for _, row in df.iterrows():
                location = row['Location']
                size = round(row['Remaining Size (mm)'], 1)
                count = int(row['Count'])
                
                key = (location, size)
                matches = inventory_matches.get(key, [])
                
                # Create rows for matches
                if matches:
                    for match in matches:
                        match_id = match['match_id']
                        group_id = match['group_id']
                        apt = match['apt']
                        loc = match['loc']
                        cut_size = match['cut_size']
                        waste = match['waste']
                        
                        inventory_rows.append({
                            'Location': location,
                            'Size (mm)': size,
                            'Match ID': match_id,
                            'Group ID': group_id,
                            'Status': 'Matched',
                            'Matched With': f"{apt}-{loc} ({cut_size}mm)",
                            'Cut Size (mm)': cut_size,
                            'Waste (mm)': waste,
                            'Piece Type': piece_type,
                            'Color': self.INV_COLOR,
                            'Direction': direction
                        })
                    count -= len(matches)
                
                # Add unmatched pieces
                if count > 0:
                    inventory_rows.append({
                        'Location': location,
                        'Size (mm)': size,
                        'Match ID': '',
                        'Group ID': '',
                        'Status': 'Unmatched',
                        'Matched With': f"{count} unmatched piece(s)",
                        'Cut Size (mm)': None,
                        'Waste (mm)': None,
                        'Piece Type': piece_type,
                        'Color': '',
                        'Direction': direction
                    })
        
        # Create DataFrame
        inventory_df = pd.DataFrame(inventory_rows)
        if not inventory_df.empty:
            inventory_df['Status_Order'] = inventory_df['Status'].map({'Matched': 0, 'Unmatched': 1})
            inventory_df = inventory_df.sort_values(by=['Location', 'Size (mm)', 'Status_Order', 'Match ID'])
            inventory_df = inventory_df.drop(columns=['Status_Order']).reset_index(drop=True)
        
        return inventory_df

    def create_group_based_tile_mapping(self, clean_tables):
        """Create mapping that groups tiles by their Group IDs properly"""
        print("🔄 Creating group-based tile mapping...")
        
        # Create mapping: Group ID -> {color, match_type, details}
        group_mapping = {}
        
        # Create mapping: (apartment, location, cut_size, remaining_size) -> [Group IDs available]
        tile_specs_to_groups = {}
        
        print(f"   📊 Processing {len(clean_tables)} clean tables...")
        
        for table_name, table_data in clean_tables.items():
            if isinstance(table_data, pd.DataFrame) and not table_data.empty:
                print(f"   📋 Processing {table_name} with {len(table_data)} rows")
                
                for _, row in table_data.iterrows():
                    apartment = row.get('Apartment', '')
                    location = row.get('Location', '')
                    cut_size = round(row.get('Cut Size', 0), 1)
                    remaining_size = round(row.get('Remaining Size', 0), 1)
                    count = int(row.get('Count', 1))
                    group_id = row.get('Group ID', '')
                    color = row.get('Color', '')
                    match_type = row.get('Match Type', '')
                    piece_type = row.get('Piece Type', '')
                    
                    if group_id and group_id != '':
                        # Store group information
                        group_mapping[group_id] = {
                            'color': color if color and color != '' else self.UNMATCHED_COLOR,
                            'match_type': match_type,
                            'piece_type': piece_type,
                            'apartment': apartment,
                            'location': location,
                            'cut_size': cut_size,
                            'remaining_size': remaining_size,
                            'count': count,
                            'source_table': table_name
                        }
                        
                        # Create reverse mapping for tile specs to groups
                        tile_spec = (apartment, location, cut_size, remaining_size, piece_type)
                        if tile_spec not in tile_specs_to_groups:
                            tile_specs_to_groups[tile_spec] = []
                        
                        # Add this group ID to the available groups for this tile spec
                        for i in range(count):
                            tile_specs_to_groups[tile_spec].append({
                                'group_id': group_id,
                                'color': color,
                                'match_type': match_type,
                                'used': False,
                                'source_table': table_name
                            })
        
        print(f"   ✅ Created {len(group_mapping)} group mappings")
        print(f"   ✅ Created {len(tile_specs_to_groups)} tile spec mappings")
        
        return group_mapping, tile_specs_to_groups

    def get_tile_color_group_based(self, tile_row, group_mapping, tile_specs_to_groups, tile_width, tile_height):
        """Get tile color using group-based matching with proper orientation handling"""
        apartment_name = tile_row['apartment_name']
        room_name = tile_row['room_name'] 
        classification = tile_row['classification']
        
        # Full and irregular tiles get their own colors
        if classification == 'full':
            return self.FULL_TILE_COLOR, 'Full Tile', ''
        elif classification == 'irregular':
            return self.IRREGULAR_COLOR, 'Irregular Tile', ''
        
        # For cut tiles, calculate dimensions and find matching group
        if classification in ['cut_x', 'cut_y', 'all_cut']:
            
            # Get the cut_side that was calculated in Step 5 (already orientation-corrected)
            cut_size = round(tile_row.get('cut_side', 0), 1)
            
            if cut_size == 0:
                return self.UNMATCHED_COLOR, 'Unmatched Cut', ''
            
            # Get actual tile dimensions
            actual_width = tile_row.get('actual_width', tile_width)
            actual_height = tile_row.get('actual_height', tile_height)
            
            # Get apartment orientation
            orientation = tile_row.get('orientation', 0)
            
            # CRITICAL FIX: Calculate remaining size based on BOTH classification AND orientation
            if classification == 'cut_x':
                # cut_x means cut in X direction
                if orientation == 90:
                    # In 90° rotated apartments, X direction maps to original Y
                    remaining_size = round(actual_height - cut_size, 1)
                else:
                    # Normal orientation
                    remaining_size = round(actual_width - cut_size, 1)
            elif classification == 'cut_y':
                # cut_y means cut in Y direction
                if orientation == 90:
                    # In 90° rotated apartments, Y direction maps to original X
                    remaining_size = round(actual_width - cut_size, 1)
                else:
                    # Normal orientation
                    remaining_size = round(actual_height - cut_size, 1)
            else:  # all_cut
                min_standard = min(actual_width, actual_height)
                remaining_size = round(min_standard - cut_size, 1)
            
            # Determine piece type using STANDARD tile dimensions (not rotated)
            half_threshold = min(tile_width, tile_height) / 2
            piece_type = 'Less than Half' if cut_size < half_threshold else 'More than Half'
            
            print(f"DEBUG: Apt: {apartment_name}, Room: {room_name}, Orient: {orientation}, Class: {classification}")
            print(f"DEBUG: Cut: {cut_size}, Remaining: {remaining_size}, Type: {piece_type}")
            
            # Create comprehensive room name variations
            room_codes = [room_name]
            
            # Enhanced room name mapping
            room_lower = room_name.lower().strip()
            room_variations = []
            
            if room_lower in ['l', 'lr', 'living']:
                room_variations.extend(['Living', 'LR', 'LIVING', 'L', 'Living Room', 'Hall'])
            elif room_lower in ['b1', 'b2', 'bt', 'bath', 'bathroom']:
                room_variations.extend(['Bathroom', 'BT', 'BATH', 'B1', 'B2', 'Toilet'])
            elif room_lower in ['mr', 'mb', 'br', 'bedroom', 'master']:
                room_variations.extend(['Bedroom', 'BR', 'BEDROOM', 'MR', 'MB', 'Master Bedroom'])
            elif room_lower in ['k', 'kt', 'kitchen']:
                room_variations.extend(['Kitchen', 'KT', 'KITCHEN', 'K'])
            elif room_lower in ['bal', 'balcony']:
                room_variations.extend(['Balcony', 'BAL', 'BALCONY'])
            else:
                room_variations.append(room_name.title())
                room_variations.append(room_name.upper())
            
            # Add apartment-prefixed versions
            for variation in list(room_variations):
                room_variations.append(f"{apartment_name}-{variation}")
            
            room_codes.extend(room_variations)
            
            # Remove duplicates while preserving order
            seen = set()
            room_codes = [x for x in room_codes if not (x in seen or seen.add(x))]
            
            # CRITICAL FIX: Only look in the correct table based on classification
            target_tables = []
            
            if classification == 'cut_x':
                target_tables = ['x_direction']
            elif classification == 'cut_y':
                target_tables = ['y_direction']
            else:  # all_cut
                target_tables = ['all_direction']
            
            # Search progressively with tolerance
            tolerances = [0, 1.0, 2.0, 5.0, 10.0]
            
            for tolerance in tolerances:
                for room_code in room_codes:
                    for p_type in [piece_type, 'Less than Half', 'More than Half']:
                        
                        if tolerance == 0:
                            # Exact match
                            key = (apartment_name, room_code, cut_size, remaining_size, p_type)
                            if key in tile_specs_to_groups:
                                for group_entry in tile_specs_to_groups[key]:
                                    # CRITICAL: Only use entries from the correct table
                                    if (not group_entry.get('used', False) and 
                                        group_entry.get('source_table') in target_tables):
                                        group_entry['used'] = True
                                        color = group_entry.get('color', self.UNMATCHED_COLOR)
                                        match_type = group_entry.get('match_type', 'Unknown')
                                        group_id = group_entry.get('group_id', '')
                                        return color, f"Matched ({match_type})", group_id
                        else:
                            # Fuzzy match with tolerance
                            for (map_apt, map_loc, map_c_size, map_r_size, map_p_type), group_entries in tile_specs_to_groups.items():
                                if (map_apt == apartment_name and 
                                    (map_loc == room_code or 
                                    map_loc.lower() == room_code.lower() or
                                    room_code.lower() in map_loc.lower() or
                                    map_loc.lower() in room_code.lower()) and
                                    abs(map_c_size - cut_size) <= tolerance and 
                                    abs(map_r_size - remaining_size) <= tolerance):
                                    
                                    for group_entry in group_entries:
                                        # CRITICAL: Only use entries from the correct table
                                        if (not group_entry.get('used', False) and 
                                            group_entry.get('source_table') in target_tables):
                                            group_entry['used'] = True
                                            color = group_entry.get('color', self.UNMATCHED_COLOR)
                                            match_type = group_entry.get('match_type', 'Unknown')
                                            group_id = group_entry.get('group_id', '')
                                            return color, f"Matched ({match_type})", group_id
        
        # Default to unmatched
        return self.UNMATCHED_COLOR, 'Unmatched Cut', ''

    def create_unmatched_summary(self, items):
        """Create summary of unmatched items"""
        agg = {}
        for item in items:
            key = (item['Apartment'], item['Location'], item['Cut Size (mm)'], item['Remaining Size (mm)'])
            agg[key] = agg.get(key, 0) + 1
        return pd.DataFrame([
            {'Apartment': key[0], 'Location': key[1], 'Cut Size (mm)': key[2], 
              'Remaining Size (mm)': key[3], 'Count': count}
            for key, count in agg.items()
        ])

    def process_cut_pieces_matching(self, cut_pieces_by_half, tolerance_ranges):
        """Enhanced with two-stage matching - Priority 1&2, then Priority 3"""
        
        # === STAGE 1: EXISTING PRIORITY 1 & 2 MATCHING ===
        print(f"\n🧩 STAGE 1: Priority 1 & 2 Matching...")
        
        has_pattern = cut_pieces_by_half['has_pattern']
        has_inventory = any('inv' in key for key in cut_pieces_by_half.keys())
        
        print(f"Has inventory: {has_inventory}")
        
        results = {}
        
        if has_pattern:
            print("\n📋 Processing Pattern Mode (X/Y cuts)...")
            
            # Process X direction
            print("\n🔄 Processing Cut X Tiles:")
            x_less_than_half = cut_pieces_by_half['x_less_than_half']
            x_more_than_half = cut_pieces_by_half['x_more_than_half']
            
            # X Inventory matching (Priority 1)
            x_inv_matches_df = pd.DataFrame()
            if has_inventory and not x_less_than_half.empty:
                x_inv_less = cut_pieces_by_half.get('x_inv_less_than_half', pd.DataFrame())
                x_inv_more = cut_pieces_by_half.get('x_inv_more_than_half', pd.DataFrame())
                
                if not x_inv_less.empty or not x_inv_more.empty:
                    x_less_expanded = self.expand_dataframe(x_less_than_half)
                    x_inv_combined = []
                    if not x_inv_less.empty:
                        x_inv_combined.extend(self.expand_dataframe(x_inv_less))
                    if not x_inv_more.empty:
                        x_inv_combined.extend(self.expand_dataframe(x_inv_more))
                    
                    x_less_expanded.sort(key=lambda x: x['Cut Size (mm)'])
                    x_inv_combined.sort(key=lambda x: x['Remaining Size (mm)'], reverse=True)
                    
                    x_inv_matches, x_less_after_inv, _ = self.match_with_inventory(
                        x_less_expanded, x_inv_combined, tolerance_ranges, "X")
                    x_inv_matches_df = pd.DataFrame(x_inv_matches)
                    print(f"Found {len(x_inv_matches_df)} X-Inventory matches")
                else:
                    x_less_after_inv = self.expand_dataframe(x_less_than_half) if not x_less_than_half.empty else []
            else:
                x_less_after_inv = self.expand_dataframe(x_less_than_half) if not x_less_than_half.empty else []
            
            # X Apartment matching (Priority 2)
            x_apt_matches_df = pd.DataFrame()
            x_unmatched_less_df = pd.DataFrame()
            x_unmatched_more_df = pd.DataFrame()
            
            if not x_less_than_half.empty and not x_more_than_half.empty:
                x_more_expanded = self.expand_dataframe(x_more_than_half)
                x_less_after_inv.sort(key=lambda x: x['Cut Size (mm)'])
                x_more_expanded.sort(key=lambda x: x['Cut Size (mm)'], reverse=True)
                
                x_apt_matches, x_unmatched_less, x_unmatched_more = self.match_with_progressive_tolerance(
                    x_less_after_inv, x_more_expanded, tolerance_ranges, "X")
                
                x_apt_matches_df = pd.DataFrame(x_apt_matches)
                x_unmatched_less_df = self.create_unmatched_summary(x_unmatched_less)
                x_unmatched_more_df = self.create_unmatched_summary(x_unmatched_more)
                print(f"Found {len(x_apt_matches_df)} X-Apartment matches")
            
            results['x_apt_matches_df'] = x_apt_matches_df
            results['x_inv_matches_df'] = x_inv_matches_df
            results['x_unmatched_less_df'] = x_unmatched_less_df
            results['x_unmatched_more_df'] = x_unmatched_more_df
            
            # Process Y direction
            print("\n🔄 Processing Cut Y Tiles:")
            y_less_than_half = cut_pieces_by_half['y_less_than_half']
            y_more_than_half = cut_pieces_by_half['y_more_than_half']
            
            # Y Inventory matching
            y_inv_matches_df = pd.DataFrame()
            if has_inventory and not y_less_than_half.empty:
                y_inv_less = cut_pieces_by_half.get('y_inv_less_than_half', pd.DataFrame())
                y_inv_more = cut_pieces_by_half.get('y_inv_more_than_half', pd.DataFrame())
                
                if not y_inv_less.empty or not y_inv_more.empty:
                    y_less_expanded = self.expand_dataframe(y_less_than_half)
                    y_inv_combined = []
                    if not y_inv_less.empty:
                        y_inv_combined.extend(self.expand_dataframe(y_inv_less))
                    if not y_inv_more.empty:
                        y_inv_combined.extend(self.expand_dataframe(y_inv_more))
                    
                    y_less_expanded.sort(key=lambda x: x['Cut Size (mm)'])
                    y_inv_combined.sort(key=lambda x: x['Remaining Size (mm)'], reverse=True)
                    
                    y_inv_matches, y_less_after_inv, _ = self.match_with_inventory(
                        y_less_expanded, y_inv_combined, tolerance_ranges, "Y")
                    y_inv_matches_df = pd.DataFrame(y_inv_matches)
                    print(f"Found {len(y_inv_matches_df)} Y-Inventory matches")
                else:
                    y_less_after_inv = self.expand_dataframe(y_less_than_half) if not y_less_than_half.empty else []
            else:
                y_less_after_inv = self.expand_dataframe(y_less_than_half) if not y_less_than_half.empty else []
            
            # Y Apartment matching (Priority 2)
            y_apt_matches_df = pd.DataFrame()
            y_unmatched_less_df = pd.DataFrame()
            y_unmatched_more_df = pd.DataFrame()
            
            if not y_less_than_half.empty and not y_more_than_half.empty:
                y_more_expanded = self.expand_dataframe(y_more_than_half)
                y_less_after_inv.sort(key=lambda x: x['Cut Size (mm)'])
                y_more_expanded.sort(key=lambda x: x['Cut Size (mm)'], reverse=True)
                
                y_apt_matches, y_unmatched_less, y_unmatched_more = self.match_with_progressive_tolerance(
                    y_less_after_inv, y_more_expanded, tolerance_ranges, "Y")
                
                y_apt_matches_df = pd.DataFrame(y_apt_matches)
                y_unmatched_less_df = self.create_unmatched_summary(y_unmatched_less)
                y_unmatched_more_df = self.create_unmatched_summary(y_unmatched_more)
                print(f"Found {len(y_apt_matches_df)} Y-Apartment matches")
            
            results['y_apt_matches_df'] = y_apt_matches_df
            results['y_inv_matches_df'] = y_inv_matches_df
            results['y_unmatched_less_df'] = y_unmatched_less_df
            results['y_unmatched_more_df'] = y_unmatched_more_df
            
        else:
            print("\n📋 Processing No Pattern Mode (All cuts)...")
            
            all_less_than_half = cut_pieces_by_half['all_less_than_half']
            all_more_than_half = cut_pieces_by_half['all_more_than_half']
            
            # All Inventory matching
            all_inv_matches_df = pd.DataFrame()
            if has_inventory and not all_less_than_half.empty:
                all_inv_less = cut_pieces_by_half.get('all_inv_less_than_half', pd.DataFrame())
                all_inv_more = cut_pieces_by_half.get('all_inv_more_than_half', pd.DataFrame())
                
                if not all_inv_less.empty or not all_inv_more.empty:
                    all_less_expanded = self.expand_dataframe(all_less_than_half)
                    all_inv_combined = []
                    if not all_inv_less.empty:
                        all_inv_combined.extend(self.expand_dataframe(all_inv_less))
                    if not all_inv_more.empty:
                        all_inv_combined.extend(self.expand_dataframe(all_inv_more))
                    
                    all_less_expanded.sort(key=lambda x: x['Cut Size (mm)'])
                    all_inv_combined.sort(key=lambda x: x['Remaining Size (mm)'], reverse=True)
                    
                    all_inv_matches, all_less_after_inv, _ = self.match_with_inventory(
                        all_less_expanded, all_inv_combined, tolerance_ranges, "All")
                    all_inv_matches_df = pd.DataFrame(all_inv_matches)
                    print(f"Found {len(all_inv_matches_df)} All-Inventory matches")
                else:
                    all_less_after_inv = self.expand_dataframe(all_less_than_half) if not all_less_than_half.empty else []
            else:
                all_less_after_inv = self.expand_dataframe(all_less_than_half) if not all_less_than_half.empty else []
            
            # All Apartment matching (Priority 2)
            all_apt_matches_df = pd.DataFrame()
            all_unmatched_less_df = pd.DataFrame()
            all_unmatched_more_df = pd.DataFrame()
            
            if not all_less_than_half.empty and not all_more_than_half.empty:
                all_more_expanded = self.expand_dataframe(all_more_than_half)
                all_less_after_inv.sort(key=lambda x: x['Cut Size (mm)'])
                all_more_expanded.sort(key=lambda x: x['Cut Size (mm)'], reverse=True)
                
                all_apt_matches, all_unmatched_less, all_unmatched_more = self.match_with_progressive_tolerance(
                    all_less_after_inv, all_more_expanded, tolerance_ranges, "All")
                
                all_apt_matches_df = pd.DataFrame(all_apt_matches)
                all_unmatched_less_df = self.create_unmatched_summary(all_unmatched_less)
                all_unmatched_more_df = self.create_unmatched_summary(all_unmatched_more)
                print(f"Found {len(all_apt_matches_df)} All-Apartment matches")
            
            results['all_apt_matches_df'] = all_apt_matches_df
            results['all_inv_matches_df'] = all_inv_matches_df
            results['all_unmatched_less_df'] = all_unmatched_less_df
            results['all_unmatched_more_df'] = all_unmatched_more_df
        
        # === STAGE 2: PRIORITY 3 ENHANCEMENT ===
        print(f"\n🧩 STAGE 2: Priority 3 Matching...")
        
        results = self.enhance_with_priority3(results, cut_pieces_by_half, tolerance_ranges)
        
        return results

    def create_clean_tables(self, matching_results, cut_pieces_by_half):
        """Create clean formatted tables from matching results"""
        print(f"\n🎨 Creating formatted reports...")
        
        clean_tables = {}
        has_pattern = cut_pieces_by_half['has_pattern']
        
        if has_pattern:
            # Create X direction report
            if 'x_apt_matches_df' in matching_results or 'x_inv_matches_df' in matching_results:
                x_report = self.create_apartment_report(
                    matching_results.get('x_apt_matches_df', pd.DataFrame()),
                    matching_results.get('x_inv_matches_df', pd.DataFrame()),
                    matching_results.get('x_unmatched_less_df', pd.DataFrame()),
                    matching_results.get('x_unmatched_more_df', pd.DataFrame()),
                    cut_pieces_by_half,
                    "X"
                )
                if x_report is not None:
                    clean_tables['x_direction'] = x_report
                    print(f"✅ Created X direction report with {len(x_report)} rows")
            
            # Create Y direction report
            if 'y_apt_matches_df' in matching_results or 'y_inv_matches_df' in matching_results:
                y_report = self.create_apartment_report(
                    matching_results.get('y_apt_matches_df', pd.DataFrame()),
                    matching_results.get('y_inv_matches_df', pd.DataFrame()),
                    matching_results.get('y_unmatched_less_df', pd.DataFrame()),
                    matching_results.get('y_unmatched_more_df', pd.DataFrame()),
                    cut_pieces_by_half,
                    "Y"
                )
                if y_report is not None:
                    clean_tables['y_direction'] = y_report
                    print(f"✅ Created Y direction report with {len(y_report)} rows")
            
            # Create inventory reports
            if 'x_inv_matches_df' in matching_results:
                x_inv_report = self.create_inventory_report(
                    matching_results['x_inv_matches_df'], 
                    cut_pieces_by_half, 
                    "X"
                )
                if x_inv_report is not None:
                    clean_tables['x_inv'] = x_inv_report
                    print(f"✅ Created X inventory report with {len(x_inv_report)} rows")
            
            if 'y_inv_matches_df' in matching_results:
                y_inv_report = self.create_inventory_report(
                    matching_results['y_inv_matches_df'], 
                    cut_pieces_by_half, 
                    "Y"
                )
                if y_inv_report is not None:
                    clean_tables['y_inv'] = y_inv_report
                    print(f"✅ Created Y inventory report with {len(y_inv_report)} rows")
        
        else:
            # Create all direction report
            if 'all_apt_matches_df' in matching_results or 'all_inv_matches_df' in matching_results:
                all_report = self.create_apartment_report(
                    matching_results.get('all_apt_matches_df', pd.DataFrame()),
                    matching_results.get('all_inv_matches_df', pd.DataFrame()),
                    matching_results.get('all_unmatched_less_df', pd.DataFrame()),
                    matching_results.get('all_unmatched_more_df', pd.DataFrame()),
                    cut_pieces_by_half,
                    "All"
                )
                if all_report is not None:
                    clean_tables['all_direction'] = all_report
                    print(f"✅ Created all direction report with {len(all_report)} rows")
            
            # Create inventory report
            if 'all_inv_matches_df' in matching_results:
                all_inv_report = self.create_inventory_report(
                    matching_results['all_inv_matches_df'], 
                    cut_pieces_by_half, 
                    "All"
                )
                if all_inv_report is not None:
                    clean_tables['all_inv'] = all_inv_report
                    print(f"✅ Created all inventory report with {len(all_inv_report)} rows")
        
        return clean_tables
    
    def enhance_with_priority3(self, existing_results, cut_pieces_by_half, tolerance_ranges):
        """Enhance existing results with Priority 3 matches"""
        
        has_pattern = cut_pieces_by_half['has_pattern']
        
        if has_pattern:
            # X Direction Priority 3
            x_unmatched = existing_results.get('x_unmatched_less_df', pd.DataFrame())
            if not x_unmatched.empty and len(x_unmatched) >= 2:
                x_new_matches, x_final_unmatched = self.apply_priority3_matching(
                    x_unmatched, "X", cut_pieces_by_half, tolerance_ranges
                )
                
                if x_new_matches:
                    # Get existing matches for proper numbering
                    existing_x = existing_results.get('x_apt_matches_df', pd.DataFrame())
                    
                    # Renumber Priority 3 matches to continue sequence
                    x_renumbered_matches = self.renumber_priority3_matches(existing_x, x_new_matches, "X")
                    
                    # Merge with existing matches
                    combined_x = pd.concat([existing_x, pd.DataFrame(x_renumbered_matches)], ignore_index=True)
                    existing_results['x_apt_matches_df'] = combined_x
                    existing_results['x_unmatched_less_df'] = x_final_unmatched
                    print(f"      X Direction: Added {len(x_new_matches)} Priority 3 matches (pairs: {len(x_new_matches)//2})")
            
            # Y Direction Priority 3
            y_unmatched = existing_results.get('y_unmatched_less_df', pd.DataFrame())
            if not y_unmatched.empty and len(y_unmatched) >= 2:
                y_new_matches, y_final_unmatched = self.apply_priority3_matching(
                    y_unmatched, "Y", cut_pieces_by_half, tolerance_ranges
                )
                
                if y_new_matches:
                    existing_y = existing_results.get('y_apt_matches_df', pd.DataFrame())
                    y_renumbered_matches = self.renumber_priority3_matches(existing_y, y_new_matches, "Y")
                    
                    combined_y = pd.concat([existing_y, pd.DataFrame(y_renumbered_matches)], ignore_index=True)
                    existing_results['y_apt_matches_df'] = combined_y
                    existing_results['y_unmatched_less_df'] = y_final_unmatched
                    print(f"      Y Direction: Added {len(y_new_matches)} Priority 3 matches (pairs: {len(y_new_matches)//2})")
        
        else:
            # All Direction Priority 3
            all_unmatched = existing_results.get('all_unmatched_less_df', pd.DataFrame())
            if not all_unmatched.empty and len(all_unmatched) >= 2:
                all_new_matches, all_final_unmatched = self.apply_priority3_matching(
                    all_unmatched, "All", cut_pieces_by_half, tolerance_ranges
                )
                
                if all_new_matches:
                    existing_all = existing_results.get('all_apt_matches_df', pd.DataFrame())
                    all_renumbered_matches = self.renumber_priority3_matches(existing_all, all_new_matches, "All")
                    
                    combined_all = pd.concat([existing_all, pd.DataFrame(all_renumbered_matches)], ignore_index=True)
                    existing_results['all_apt_matches_df'] = combined_all
                    existing_results['all_unmatched_less_df'] = all_final_unmatched
                    print(f"      All Direction: Added {len(all_new_matches)} Priority 3 matches (pairs: {len(all_new_matches)//2})")
        
        return existing_results
    
    def debug_priority3_matches(self, matches_df, direction="All"):
        """Debug function to verify Priority 3 matches are created correctly"""
        
        if matches_df.empty:
            return
        
        priority3_matches = matches_df[matches_df.get('_is_priority3', False) == True]
        
        if not priority3_matches.empty:
            print(f"\n🔍 DEBUG: Priority 3 matches in {direction} direction:")
            
            # Group by Match ID to show pairs
            for match_id in priority3_matches['Match ID'].unique():
                pair_matches = priority3_matches[priority3_matches['Match ID'] == match_id]
                print(f"   Match {match_id}: {len(pair_matches)} pieces")
                
                for _, match in pair_matches.iterrows():
                    role = match.get('_priority3_piece_role', 'unknown')
                    print(f"     {role}: {match['Small Piece Apt']}-{match['Small Piece Loc']} ({match['Small Piece Size']}mm)")
        else:
            print(f"\n🔍 DEBUG: No Priority 3 matches found in {direction} direction")

    def apply_priority3_matching(self, unmatched_less_df, direction, cut_pieces_by_half, tolerance_ranges):
        """Apply Priority 3 matching and return matches in same format as Priority 2"""
        
        if unmatched_less_df.empty:
            return [], unmatched_less_df
        
        tile_width = cut_pieces_by_half['tile_width']
        tile_height = cut_pieces_by_half['tile_height']
        
        # Step 1: Create pairs from unmatched pieces
        pairs, remaining_pieces = self.create_priority_3_pairs(unmatched_less_df, direction, tile_width, tile_height)
        
        if not pairs:
            return [], unmatched_less_df
        
        print(f"      Priority 3 {direction}: Created {len(pairs)} pairs from {len(unmatched_less_df)} pieces")
        
        # Step 2: Convert pairs to matches in SAME FORMAT as Priority 2
        # Create TWO match entries per pair (one for each piece) with SAME Match ID
        priority3_matches = []
        
        for i, pair in enumerate(pairs):
            # Determine target dimension for remaining calculation
            if direction == "X":
                target_dimension = tile_width
            elif direction == "Y":
                target_dimension = tile_height
            else:
                target_dimension = min(tile_width, tile_height)
            
            # Generate shared Match ID for both pieces in the pair
            shared_match_id = f'P3-{direction}-{i+1}'
            
            # Create match entry for PIECE 1
            match_entry_1 = {
                'Match ID': shared_match_id,
                'Small Piece Apt': pair['piece1_apt'],
                'Small Piece Loc': pair['piece1']['Location'], 
                'Small Piece Size': pair['piece1_size'],
                'Small Piece Remain': target_dimension - pair['piece1_size'],
                'Large Piece Apt': pair['piece2_apt'],  # Partner apartment
                'Large Piece Loc': pair['piece2']['Location'],  # Partner location
                'Large Piece Size': pair['piece2_size'],  # Partner size
                'Waste': pair['waste'],
                'Tolerance Range': f"Priority 3 pairing",
                'Same Apartment': pair['piece1_apt'] == pair['piece2_apt'],
                '_is_priority3': True,
                '_priority3_pair_id': i,
                '_priority3_piece_role': 'piece1'
            }
            
            # Create match entry for PIECE 2 (with roles swapped)
            match_entry_2 = {
                'Match ID': shared_match_id,
                'Small Piece Apt': pair['piece2_apt'],
                'Small Piece Loc': pair['piece2']['Location'], 
                'Small Piece Size': pair['piece2_size'],
                'Small Piece Remain': target_dimension - pair['piece2_size'],
                'Large Piece Apt': pair['piece1_apt'],  # Partner apartment
                'Large Piece Loc': pair['piece1']['Location'],  # Partner location
                'Large Piece Size': pair['piece1_size'],  # Partner size
                'Waste': pair['waste'],
                'Tolerance Range': f"Priority 3 pairing",
                'Same Apartment': pair['piece1_apt'] == pair['piece2_apt'],
                '_is_priority3': True,
                '_priority3_pair_id': i,
                '_priority3_piece_role': 'piece2'
            }
            
            priority3_matches.append(match_entry_1)
            priority3_matches.append(match_entry_2)
        
        return priority3_matches, remaining_pieces

    def create_priority_3_pairs(self, less_pieces_df, direction="X", tile_width=600, tile_height=600):
        """Create pairs from less-than-half pieces DataFrame"""
        
        if less_pieces_df.empty:
            return [], pd.DataFrame()
        
        # Get target dimension
        if direction == "X":
            target_dimension = tile_width
        elif direction == "Y": 
            target_dimension = tile_height
        else:  # all_cut
            target_dimension = min(tile_width, tile_height)
        
        max_waste = target_dimension / 3  # 200mm for 600mm tile
        
        # Expand pieces with counts
        expanded_pieces = self.expand_pieces_with_counts(less_pieces_df)
        
        if len(expanded_pieces) < 2:
            return [], less_pieces_df
        
        # Generate all valid combinations
        combinations = []
        for i in range(len(expanded_pieces)):
            for j in range(i + 1, len(expanded_pieces)):
                piece1 = expanded_pieces[i]
                piece2 = expanded_pieces[j]
                size1 = piece1['Cut Size (mm)']
                size2 = piece2['Cut Size (mm)']
                
                combined = size1 + size2
                waste = target_dimension - combined
                
                if 0 <= waste <= max_waste:
                    combinations.append({
                        'piece1': piece1,
                        'piece2': piece2,
                        'piece1_size': size1,
                        'piece2_size': size2,
                        'piece1_apt': piece1['Apartment'],
                        'piece2_apt': piece2['Apartment'],
                        'combined_size': combined,
                        'waste': waste,
                        'piece1_idx': i,
                        'piece2_idx': j
                    })
        
        # Sort by waste (best matches first)
        combinations.sort(key=lambda x: x['waste'])
        
        # Select non-overlapping pairs
        used_indices = set()
        selected_pairs = []
        
        for combo in combinations:
            if combo['piece1_idx'] not in used_indices and combo['piece2_idx'] not in used_indices:
                selected_pairs.append(combo)
                used_indices.add(combo['piece1_idx'])
                used_indices.add(combo['piece2_idx'])
        
        # Create remaining pieces summary (back to count format)
        remaining_expanded = [expanded_pieces[i] for i in range(len(expanded_pieces)) if i not in used_indices]
        remaining_summary = self.create_unmatched_summary(remaining_expanded)
        
        return selected_pairs, remaining_summary

    def expand_pieces_with_counts(self, cut_pieces_input):
        """Convert count-based input to individual pieces - handles both DataFrame and list"""
        expanded_pieces = []
        
        # Handle DataFrame input
        if hasattr(cut_pieces_input, 'iterrows'):
            for _, row in cut_pieces_input.iterrows():
                count = int(row.get('Count', 1))
                for i in range(count):
                    expanded_piece = row.to_dict()
                    expanded_piece['piece_id'] = f"{row['Apartment']}-{row['Location']}-{row['Cut Size (mm)']}-{i+1}"
                    expanded_pieces.append(expanded_piece)
        
        # Handle list input
        elif isinstance(cut_pieces_input, list):
            for piece in cut_pieces_input:
                if isinstance(piece, dict):
                    count = int(piece.get('Count', 1))
                    for i in range(count):
                        expanded_piece = piece.copy()
                        expanded_piece['piece_id'] = f"{piece['Apartment']}-{piece['Location']}-{piece['Cut Size (mm)']}-{i+1}"
                        expanded_pieces.append(expanded_piece)
                else:
                    print(f"Warning: Unexpected piece type: {type(piece)}")
        
        else:
            print(f"Warning: Unexpected input type: {type(cut_pieces_input)}")
            return []
        
        return expanded_pieces
    
    def renumber_priority3_matches(self, existing_matches_df, priority3_matches, direction):
        """Renumber Priority 3 matches to continue sequence from existing matches"""
        
        if not priority3_matches:
            return priority3_matches
        
        # Find the highest existing match number for this direction
        if direction == "X":
            pattern = r'^X(\d+)$'
        elif direction == "Y":
            pattern = r'^Y(\d+)$'
        else:  # All
            pattern = r'^XY(\d+)$'
        
        max_existing_num = 0
        if not existing_matches_df.empty:
            for match_id in existing_matches_df['Match ID']:
                import re
                match = re.match(pattern, str(match_id))
                if match:
                    num = int(match.group(1))
                    max_existing_num = max(max_existing_num, num)
        
        # Renumber Priority 3 matches
        renumbered_matches = []
        pair_counter = max_existing_num + 1
        current_pair_id = None
        
        for match in priority3_matches:
            pair_id = match.get('_priority3_pair_id', 0)
            
            # If this is a new pair, increment counter
            if current_pair_id != pair_id:
                current_pair_id = pair_id
                if direction == "X":
                    new_match_id = f"X{pair_counter}"
                elif direction == "Y":
                    new_match_id = f"Y{pair_counter}"
                else:
                    new_match_id = f"XY{pair_counter}"
                pair_counter += 1
            
            # Update the match with new ID
            updated_match = match.copy()
            updated_match['Match ID'] = new_match_id
            renumbered_matches.append(updated_match)
        
        return renumbered_matches