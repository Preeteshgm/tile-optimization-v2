import numpy as np
import pandas as pd
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
import math
import traceback

from processors.utility_functions import display_dataframe

class TileProcessor:
    def __init__(self):
        pass

    def generate_tile_grid(self, room_poly, orientation=0, start_point=None, tile_size=(600, 600),
                      stagger_percent=0, stagger_direction='x', room_id=-1,
                      grout_thickness=3, sp_includes_grout=True):
        """Generate grid-aligned tiles with FIXED start point positioning"""
        
        # Process tile dimensions based on whether SP includes grout
        # All calculations in MILLIMETERS (keeping your existing units)
        if sp_includes_grout:
            layout_tw, layout_th = tile_size  # Layout size (with grout) in mm
            actual_tile_width = tile_size[0] - grout_thickness  # Factory size in mm
            actual_tile_height = tile_size[1] - grout_thickness  # Factory size in mm
        else:
            actual_tile_width, actual_tile_height = tile_size  # Factory size in mm
            layout_tw = tile_size[0] + grout_thickness  # Layout size (with grout) in mm
            layout_th = tile_size[1] + grout_thickness  # Layout size (with grout) in mm

        # Process start_point - KEEP EXACT COORDINATES
        if start_point is None:
            # Use room centroid if no start point provided
            centroid = room_poly.centroid
            sx, sy = centroid.x, centroid.y
            print(f"  Using room centroid as start point: ({sx:.3f}, {sy:.3f})")
        else:
            if isinstance(start_point, Point):
                sx, sy = start_point.x, start_point.y
            else:
                sx, sy = start_point[0], start_point[1]
            print(f"  Using PROVIDED start point: ({sx:.3f}, {sy:.3f}) - EXACT POSITION")

        # Apply orientation to layout and actual tile sizes
        if orientation == 90:
            layout_tw, layout_th = layout_th, layout_tw
            actual_tile_width, actual_tile_height = actual_tile_height, actual_tile_width
            # Flip stagger direction if orientation is 90°
            stagger_direction = 'y' if stagger_direction == 'x' else 'x'

        # Calculate stagger size
        stagger_size = layout_tw * stagger_percent if stagger_direction == 'x' else layout_th * stagger_percent

        room_tiles = []

        # Get room bounds with extension for complete coverage
        minx, miny, maxx, maxy = room_poly.bounds
        extension = max(layout_tw, layout_th) * 3  # Generous extension
        
        print(f"  Layout tile size: {layout_tw:.3f} x {layout_th:.3f} mm")
        print(f"  Actual tile size: {actual_tile_width:.3f} x {actual_tile_height:.3f} mm")

        # CORRECT APPROACH: Generate grid with start_point as one of the tile centers
        # Calculate how many tiles we need in each direction from the start point
        tiles_left = int((sx - (minx - extension)) / layout_tw) + 2
        tiles_right = int(((maxx + extension) - sx) / layout_tw) + 2
        tiles_down = int((sy - (miny - extension)) / layout_th) + 2
        tiles_up = int(((maxy + extension) - sy) / layout_th) + 2

        print(f"  Grid extent: {tiles_left} left, {tiles_right} right, {tiles_down} down, {tiles_up} up from start point")

        # Generate tiles with stagger logic
        if stagger_direction == 'x':
            # Horizontal staggering
            for row in range(-tiles_down, tiles_up + 1):
                y = sy + (row * layout_th)
                
                # Calculate stagger offset for this row
                x_offset = stagger_size if (row % 2 == 1 and stagger_percent > 0) else 0
                
                for col in range(-tiles_left, tiles_right + 1):
                    x = sx + (col * layout_tw) + x_offset
                    
                    # Center of this tile
                    cx, cy = x, y

                    # Create the layout tile polygon (with grout) for coverage calculations
                    layout_tile = Polygon([
                        (cx - layout_tw / 2, cy - layout_th / 2),
                        (cx + layout_tw / 2, cy - layout_th / 2),
                        (cx + layout_tw / 2, cy + layout_th / 2),
                        (cx - layout_tw / 2, cy + layout_th / 2)
                    ])

                    # Create the actual tile polygon (factory size without grout)
                    actual_tile = Polygon([
                        (cx - actual_tile_width / 2, cy - actual_tile_height / 2),
                        (cx + actual_tile_width / 2, cy - actual_tile_height / 2),
                        (cx + actual_tile_width / 2, cy + actual_tile_height / 2),
                        (cx - actual_tile_width / 2, cy + actual_tile_height / 2)
                    ])

                    # Process the tile if it intersects with the room
                    if layout_tile.is_valid and layout_tile.intersects(room_poly):
                        layout_intersection = layout_tile.intersection(room_poly)
                        if not layout_intersection.is_empty and layout_intersection.area > 0:
                            if actual_tile.intersects(room_poly):
                                actual_intersection = actual_tile.intersection(room_poly)
                                is_full = actual_intersection.equals(actual_tile)

                                # Special marking for the start point tile
                                is_start_tile = (col == 0 and row == 0)
                                
                                room_tiles.append({
                                    'polygon': actual_intersection,
                                    'layout_polygon': layout_intersection,
                                    'room_id': room_id,
                                    'width': layout_tw,
                                    'height': layout_th,
                                    'actual_tile_width': actual_tile_width,
                                    'actual_tile_height': actual_tile_height,
                                    'centroid': (cx, cy),
                                    'area': actual_intersection.area,
                                    'type': 'full' if is_full else 'cut',
                                    'orientation': orientation,
                                    'grout_thickness': grout_thickness,
                                    'is_start_tile': is_start_tile,
                                    'grid_position': (col, row)
                                })
                                
                                if is_start_tile:
                                    print(f"  ✓ Start point tile placed at EXACT position: ({cx:.3f}, {cy:.3f})")

        else:  # stagger_direction == 'y'
            # Vertical staggering
            for col in range(-tiles_left, tiles_right + 1):
                x = sx + (col * layout_tw)
                
                # Calculate stagger offset for this column
                y_offset = stagger_size if (col % 2 == 1 and stagger_percent > 0) else 0
                
                for row in range(-tiles_down, tiles_up + 1):
                    y = sy + (row * layout_th) + y_offset
                    
                    # Center of this tile
                    cx, cy = x, y

                    layout_tile = Polygon([
                        (cx - layout_tw / 2, cy - layout_th / 2),
                        (cx + layout_tw / 2, cy - layout_th / 2),
                        (cx + layout_tw / 2, cy + layout_th / 2),
                        (cx - layout_tw / 2, cy + layout_th / 2)
                    ])

                    actual_tile = Polygon([
                        (cx - actual_tile_width / 2, cy - actual_tile_height / 2),
                        (cx + actual_tile_width / 2, cy - actual_tile_height / 2),
                        (cx + actual_tile_width / 2, cy + actual_tile_height / 2),
                        (cx - actual_tile_width / 2, cy + actual_tile_height / 2)
                    ])

                    if layout_tile.is_valid and layout_tile.intersects(room_poly):
                        layout_intersection = layout_tile.intersection(room_poly)
                        if not layout_intersection.is_empty and layout_intersection.area > 0:
                            if actual_tile.intersects(room_poly):
                                actual_intersection = actual_tile.intersection(room_poly)
                                is_full = actual_intersection.equals(actual_tile)

                                is_start_tile = (col == 0 and row == 0)

                                room_tiles.append({
                                    'polygon': actual_intersection,
                                    'layout_polygon': layout_intersection,
                                    'room_id': room_id,
                                    'width': layout_tw,
                                    'height': layout_th,
                                    'actual_tile_width': actual_tile_width,
                                    'actual_tile_height': actual_tile_height,
                                    'centroid': (cx, cy),
                                    'area': actual_intersection.area,
                                    'type': 'full' if is_full else 'cut',
                                    'orientation': orientation,
                                    'grout_thickness': grout_thickness,
                                    'is_start_tile': is_start_tile,
                                    'grid_position': (col, row)
                                })
                                
                                if is_start_tile:
                                    print(f"  ✓ Start point tile placed at EXACT position: ({cx:.3f}, {cy:.3f})")

        # Verify coverage
        room_area = room_poly.area
        combined_tiles = None
        for tile in room_tiles:
            poly = tile['layout_polygon']
            if combined_tiles is None:
                combined_tiles = poly
            else:
                try:
                    combined_tiles = combined_tiles.union(poly)
                except:
                    try:
                        combined_tiles = combined_tiles.buffer(0).union(poly.buffer(0))
                    except:
                        continue

        if combined_tiles:
            coverage_pct = (combined_tiles.area / room_area) * 100
            print(f"  Room coverage: {coverage_pct:.2f}%")
            if coverage_pct < 99.5:
                print(f"⚠️ Warning: Tiles cover only {coverage_pct:.2f}% of the room area")

        print(f"  Generated {len(room_tiles)} tiles for room {room_id}")
        
        # Verify start point tile exists
        start_tiles = [t for t in room_tiles if t.get('is_start_tile', False)]
        if start_tiles:
            print(f"  ✅ Start point tile confirmed at: {start_tiles[0]['centroid']}")
        elif start_point is not None:
            print(f"  ⚠️ Warning: No start point tile generated (start point may be outside room)")
        
        return room_tiles

    def generate_tiles_for_all_rooms(self, room_df, apartment_orientations, start_points=None,
                                    stagger_percent=0, stagger_direction='x',
                                    grout_thickness=3, sp_includes_grout=True, tile_width=600, tile_height=600):
        """Process all rooms to generate tiles with explicit grout spacing"""
        print("🔄 Processing tiles for all rooms...")

        apartments_data = {}

        for _, room in room_df.iterrows():
            apartment_name = room['apartment_name']
            room_name = room['room_name']
            room_id = room['room_id']
            room_poly = room['polygon']

            # Get orientation for this apartment
            orientation = apartment_orientations[
                apartment_orientations['apartment_name'] == apartment_name
            ]['orientation'].values[0]

            # Find start point and tile size for this room
            start_point = None
            tile_size = (tile_width, tile_height)  # Use provided default
            if start_points:
                for sp in start_points:
                    if 'room_id' in sp and sp['room_id'] == room_id:
                        start_point = Point(sp['centroid'])
                        tile_size = (sp['width'], sp['height'])
                        break

            tiles = self.generate_tile_grid(
                room_poly, orientation, start_point, tile_size, 
                stagger_percent, stagger_direction, room_id, 
                grout_thickness, sp_includes_grout
            )

            # Store tiles
            if apartment_name not in apartments_data:
                apartments_data[apartment_name] = {
                    'orientation': orientation,
                    'tiles': []
                }
            apartments_data[apartment_name]['tiles'].extend(tiles)

        total_tiles = sum(len(apt_data['tiles']) for apt_name, apt_data in apartments_data.items())
        print(f"✅ Processed {len(apartments_data)} apartments with {total_tiles} total tiles")
        
        return apartments_data

    def verify_room_coverage(self, apartments_data, room_df):
        """Verify that tiles completely cover each room"""
        print("\n📋 Verifying room coverage...")
        
        coverage_results = []
        
        for _, room in room_df.iterrows():
            room_id = room['room_id']
            apartment_name = room['apartment_name']
            room_name = room['room_name']
            room_poly = room['polygon']
            room_area = room_poly.area
            
            # Get all tiles for this room
            room_tiles = []
            for apt_name, apt_data in apartments_data.items():
                for tile in apt_data['tiles']:
                    if tile['room_id'] == room_id:
                        room_tiles.append(tile)
            
            # Calculate coverage
            combined_tiles = None
            if room_tiles:
                for tile in room_tiles:
                    poly = tile.get('layout_polygon', tile['polygon'])
                    if combined_tiles is None:
                        combined_tiles = poly
                    else:
                        try:
                            combined_tiles = combined_tiles.union(poly)
                        except:
                            try:
                                combined_tiles = combined_tiles.buffer(0).union(poly.buffer(0))
                            except:
                                continue
                
                if combined_tiles:
                    coverage_pct = (combined_tiles.area / room_area) * 100
                else:
                    coverage_pct = 0
            else:
                coverage_pct = 0
            
            coverage_results.append({
                'room_id': room_id,
                'apartment_name': apartment_name,
                'room_name': room_name,
                'room_area': room_area,
                'coverage_pct': coverage_pct,
                'tile_count': len(room_tiles)
            })
        
        coverage_df = pd.DataFrame(coverage_results)
        print("\n📊 Room Coverage Results:")
        display_dataframe(coverage_df, "Coverage Results")
        
        # Check for low coverage
        low_coverage = coverage_df[coverage_df['coverage_pct'] < 99]
        if len(low_coverage) > 0:
            print(f"\n⚠️ Warning: {len(low_coverage)} rooms have less than 99% coverage")
        else:
            print("\n✅ All rooms have at least 99% coverage!")
        
        print(f"\nAverage coverage: {coverage_df['coverage_pct'].mean():.2f}%")
        print(f"Minimum coverage: {coverage_df['coverage_pct'].min():.2f}%")
        
        return coverage_df

    def optimize_tile_classification(self, apartments_data, final_room_df, has_pattern=False):
        """Optimized and simplified tile classification to handle both pattern and no-pattern cases"""
        print(f"🔄 Classifying tiles with {'pattern consideration' if has_pattern else 'flat tile (no pattern) assumption'}...")
        
        # Create a list to hold all tile data
        all_tiles = []
        
        # Track total tiles for verification
        total_tiles = 0
        
        # Calculate grout thickness from the first tile
        grout_thickness = 3  # Default
        for apt_name, apt_data in apartments_data.items():
            if apt_data['tiles']:
                first_tile = apt_data['tiles'][0]
                if 'width' in first_tile and 'actual_tile_width' in first_tile:
                    grout_thickness = first_tile['width'] - first_tile['actual_tile_width']
                    break
        
        print(f"✅ Using grout thickness: {grout_thickness} mm")
        
        # Process each apartment and its tiles
        for apt_name, apt_data in apartments_data.items():
            orientation = apt_data['orientation']
            total_tiles += len(apt_data['tiles'])
            
            for tile_idx, tile in enumerate(apt_data['tiles']):
                # Get room information
                room_id = tile['room_id']
                
                # Find room in room_df
                room_row = final_room_df[final_room_df['room_id'] == room_id]
                if not room_row.empty:
                    room_name = room_row['room_name'].values[0]
                else:
                    room_name = f"Room {room_id}"
                
                # Get polygon and measurements
                polygon = tile['polygon']
                if polygon is None:
                    continue
                    
                # Get dimensions
                width = tile.get('width', 0)
                height = tile.get('height', 0)
                actual_width = tile.get('actual_tile_width', width - grout_thickness)
                actual_height = tile.get('actual_tile_height', height - grout_thickness)
                    
                # Measured dimensions
                if isinstance(polygon, Polygon):
                    minx, miny, maxx, maxy = polygon.bounds
                    measured_width = maxx - minx
                    measured_height = maxy - miny
                elif isinstance(polygon, MultiPolygon):
                    minx, miny, maxx, maxy = polygon.bounds
                    measured_width = maxx - minx
                    measured_height = maxy - miny
                else:
                    continue
                
                # Count sides
                if isinstance(polygon, Polygon):
                    sides = len(list(polygon.exterior.coords)) - 1
                elif isinstance(polygon, MultiPolygon):
                    largest = max(polygon.geoms, key=lambda p: p.area)
                    sides = len(list(largest.exterior.coords)) - 1
                else:
                    sides = 0
                
                # Apply apartment orientation to determine expected dimensions
                if orientation == 90:
                    expected_width = actual_height
                    expected_height = actual_width
                else:
                    expected_width = actual_width
                    expected_height = actual_height
                
                # Classification tolerance (1%)
                tolerance = 0.01
                
                # Check if the tile is full-sized in either dimension
                width_ratio = measured_width / expected_width if expected_width > 0 else 0
                height_ratio = measured_height / expected_height if expected_height > 0 else 0
                
                is_full_width = abs(1.0 - width_ratio) <= tolerance
                is_full_height = abs(1.0 - height_ratio) <= tolerance
                
                # Classification logic with improved orientation handling
                if sides > 4:
                    # Irregular tiles
                    classification = 'irregular'
                    cut_side = None
                elif is_full_width and is_full_height:
                    # Full tiles
                    classification = 'full'
                    cut_side = None
                elif has_pattern:
                    # With pattern: separate cut_x and cut_y
                    # Adjust classification based on apartment orientation
                    if orientation == 90:
                        # In 90-degree rotated apartments, X and Y are swapped
                        if is_full_width:
                            # Full width in rotated space means full Y in original space
                            classification = 'cut_x'  # Cut in X direction in original space
                            cut_side = round(measured_height)
                        elif is_full_height:
                            # Full height in rotated space means full X in original space
                            classification = 'cut_y'  # Cut in Y direction in original space
                            cut_side = round(measured_width)
                        else:
                            # Cut in both directions - use SMALLER dimension (FIXED)
                            classification = 'cut_x' if measured_height <= measured_width else 'cut_y'
                            cut_side = min(round(measured_width), round(measured_height))
                    else:
                        # Normal orientation (0, 180, 270 etc.) - original logic
                        if is_full_width:
                            # Full width, cut height
                            classification = 'cut_y'
                            cut_side = round(measured_height)
                        elif is_full_height:
                            # Full height, cut width
                            classification = 'cut_x'
                            cut_side = round(measured_width)
                        else:
                            # Cut in both directions - use SMALLER dimension (FIXED)
                            classification = 'cut_x' if measured_width <= measured_height else 'cut_y'
                            cut_side = min(round(measured_width), round(measured_height))
                else:
                    # No pattern: all cuts in one list
                    classification = 'all_cut'
                    
                    if is_full_width:
                        # Cut in height (Y direction)
                        cut_side = round(measured_height)
                    elif is_full_height:
                        # Cut in width (X direction)
                        cut_side = round(measured_width)
                    else:
                        # Cut in both directions - use SMALLER dimension (FIXED)
                        cut_side = min(round(measured_width), round(measured_height))
                
                # Store all tile data
                all_tiles.append({
                    'apartment_name': apt_name,
                    'room_id': room_id,
                    'room_name': room_name,
                    'tile_index': tile_idx,
                    'polygon': polygon,
                    'orientation': orientation,
                    'measured_width': measured_width,
                    'measured_height': measured_height,
                    'width': width,
                    'height': height,
                    'actual_width': actual_width,
                    'actual_height': actual_height,
                    'is_full_width': is_full_width,
                    'is_full_height': is_full_height,
                    'classification': classification,
                    'sides': sides,
                    'cut_side': cut_side if classification in ['cut_x', 'cut_y', 'all_cut'] else None
                })
        
        # Convert to DataFrame
        tiles_df = pd.DataFrame(all_tiles)
        
        # Verify all tiles were preserved
        print(f"✅ Processed {len(tiles_df)} tiles out of {total_tiles} total")
        
        # Create classification subsets
        full_tiles = tiles_df[tiles_df['classification'] == 'full'].copy()
        irregular_tiles = tiles_df[tiles_df['classification'] == 'irregular'].copy()
        
        # Generate tile summary data
        if has_pattern:
            # With pattern: separate cut_x and cut_y
            cut_x_tiles = tiles_df[tiles_df['classification'] == 'cut_x'].copy()
            cut_y_tiles = tiles_df[tiles_df['classification'] == 'cut_y'].copy()
            all_cut_tiles = pd.DataFrame()  # Empty
            
            # Create cut summaries
            cut_x_summary = []
            for _, tile in cut_x_tiles.iterrows():
                cut_x_summary.append({
                    'APPARTMENT NUMBER': tile['apartment_name'],
                    'TILE TYPE': 'TL-1',
                    'CUT DIRECTION': 'X_DIRECTION',
                    'TILE SIZE(mm)': f"{tile['cut_side']} x {round(tile['measured_height'])}",
                    'CUT SIDE': tile['cut_side'],
                    'LOCATION': tile['room_name'],
                    'COUNT': 1
                })
            
            cut_y_summary = []
            for _, tile in cut_y_tiles.iterrows():
                cut_y_summary.append({
                    'APPARTMENT NUMBER': tile['apartment_name'],
                    'TILE TYPE': 'TL-1',
                    'CUT DIRECTION': 'Y_DIRECTION',
                    'TILE SIZE(mm)': f"{round(tile['measured_width'])} x {tile['cut_side']}",
                    'CUT SIDE': tile['cut_side'],
                    'LOCATION': tile['room_name'],
                    'COUNT': 1
                })
            
            # Convert to DataFrames
            cut_x_df = pd.DataFrame(cut_x_summary) if cut_x_summary else pd.DataFrame()
            cut_y_df = pd.DataFrame(cut_y_summary) if cut_y_summary else pd.DataFrame()
            all_cut_df = pd.DataFrame()  # Empty
            
            # Group by apartment, location, and dimensions to get counts
            if not cut_x_df.empty:
                cut_x_df = cut_x_df.groupby(['APPARTMENT NUMBER', 'TILE TYPE', 'CUT DIRECTION', 'TILE SIZE(mm)', 'CUT SIDE', 'LOCATION']).sum().reset_index()
                cut_x_df = cut_x_df.sort_values('CUT SIDE')
            
            if not cut_y_df.empty:
                cut_y_df = cut_y_df.groupby(['APPARTMENT NUMBER', 'TILE TYPE', 'CUT DIRECTION', 'TILE SIZE(mm)', 'CUT SIDE', 'LOCATION']).sum().reset_index()
                cut_y_df = cut_y_df.sort_values('CUT SIDE')
            
            # Generate cut type summaries
            cut_x_types = cut_x_tiles.groupby('cut_side').size().reset_index(name='count')
            cut_y_types = cut_y_tiles.groupby('cut_side').size().reset_index(name='count')
            
            # Sort by cut side
            if not cut_x_types.empty:
                cut_x_types = cut_x_types.sort_values('cut_side')
            if not cut_y_types.empty:
                cut_y_types = cut_y_types.sort_values('cut_side')
            
            all_cut_types = pd.DataFrame()  # Empty
            
        else:
            # No pattern: all cuts in one list
            all_cut_tiles = tiles_df[tiles_df['classification'] == 'all_cut'].copy()
            cut_x_tiles = pd.DataFrame()  # Empty
            cut_y_tiles = pd.DataFrame()  # Empty
            
            # Create all cut summary
            all_cut_summary = []
            for _, tile in all_cut_tiles.iterrows():
                all_cut_summary.append({
                    'APPARTMENT NUMBER': tile['apartment_name'],
                    'TILE TYPE': 'TL-1',
                    'CUT DIMENSION': tile['cut_side'],
                    'LOCATION': tile['room_name'],
                    'COUNT': 1
                })
            
            # Convert to DataFrame
            all_cut_df = pd.DataFrame(all_cut_summary) if all_cut_summary else pd.DataFrame()
            cut_x_df = pd.DataFrame()  # Empty
            cut_y_df = pd.DataFrame()  # Empty
            
            # Group by apartment, location, and dimensions to get counts
            if not all_cut_df.empty:
                all_cut_df = all_cut_df.groupby(['APPARTMENT NUMBER', 'TILE TYPE', 'CUT DIMENSION', 'LOCATION']).sum().reset_index()
                all_cut_df = all_cut_df.sort_values('CUT DIMENSION')
            
            # Generate all cut types summary
            all_cut_types = all_cut_tiles.groupby('cut_side').size().reset_index(name='count')
            
            # Sort by cut side
            if not all_cut_types.empty:
                all_cut_types = all_cut_types.sort_values('cut_side')
                all_cut_types.rename(columns={'cut_side': 'cut_dim'}, inplace=True)
            
            cut_x_types = pd.DataFrame()  # Empty
            cut_y_types = pd.DataFrame()  # Empty
        
        # Calculate statistics
        stats = {
            'total_tiles': len(tiles_df),
            'full_tiles': len(full_tiles),
            'irregular_tiles': len(irregular_tiles),
            'cut_x_tiles': len(cut_x_tiles),
            'cut_y_tiles': len(cut_y_tiles),
            'all_cut_tiles': len(all_cut_tiles),
            'cut_x_types': cut_x_types,
            'cut_y_types': cut_y_types,
            'all_cut_types': all_cut_types,
            'grout_thickness': grout_thickness,
            'has_pattern': has_pattern
        }
        
        return tiles_df, full_tiles, irregular_tiles, cut_x_tiles, cut_y_tiles, all_cut_tiles, cut_x_df, cut_y_df, all_cut_df, stats

    def identify_and_list_multipolygons(self, apartments_data):
        """Identify and list only the actual tile MultiPolygons (not layout polygons)"""
        print("\n🔍 Identifying MultiPolygon tiles...")
        
        multipolygon_tiles = []
        total_tiles = 0
        
        # Loop through all apartments and their tiles
        for apt_name, apt_data in apartments_data.items():
            for tile_idx, tile in enumerate(apt_data['tiles']):
                total_tiles += 1
                
                # Check ONLY the 'polygon' property (actual tile)
                if isinstance(tile['polygon'], MultiPolygon):
                    # Calculate details about this MultiPolygon
                    parts = list(tile['polygon'].geoms)
                    areas = [part.area for part in parts]
                    
                    multipolygon_info = {
                        'apartment_name': apt_name,
                        'room_id': tile['room_id'],
                        'tile_index': tile_idx,
                        'parts_count': len(parts),
                        'total_area': tile['polygon'].area,
                        'parts_areas': areas,
                        'max_part_area': max(areas) if areas else 0,
                        'max_part_percent': (max(areas) / tile['polygon'].area * 100) if areas and tile['polygon'].area > 0 else 0,
                        'is_full': tile['type'] == 'full',
                        'centroid_x': tile['centroid'][0] if 'centroid' in tile else None,
                        'centroid_y': tile['centroid'][1] if 'centroid' in tile else None
                    }
                    multipolygon_tiles.append(multipolygon_info)
        
        # Convert to DataFrame for analysis and display
        mp_df = pd.DataFrame(multipolygon_tiles)
        
        # Display detailed information
        if not mp_df.empty:
            # Create a clean display version without parts_areas column
            display_df = mp_df.drop(columns=['parts_areas'], errors='ignore')
            
            # Add tile_id column for better identification
            display_df['tile_id'] = display_df.apply(
                lambda row: f"{row['apartment_name']}-R{row['room_id']}-T{row['tile_index']}", axis=1
            )
            
            # Reorder columns
            display_cols = ['tile_id', 'apartment_name', 'room_id', 'tile_index', 
                        'parts_count', 'total_area', 'max_part_area', 'max_part_percent', 'is_full']
            
            # Only include columns that exist in the dataframe
            display_cols = [col for col in display_cols if col in display_df.columns]
            display_df = display_df[display_cols]
            
            # Print summary
            print(f"Found {len(mp_df)} MultiPolygon instances out of {total_tiles} total tiles ({(len(mp_df)/total_tiles)*100:.2f}%)")
            
            # Display the detailed table
            print("\n📋 MultiPolygon Tiles Details:")
            display_dataframe(display_df, "MultiPolygon Details")
            
        else:
            print("No MultiPolygons found in the tile geometries!")
        
        return mp_df

    def repair_multipolygons(self, apartments_data, mp_df, repair_strategy='largest_part'):
        """Repair MultiPolygon tiles using the specified strategy"""
        print(f"\n🔧 Repairing MultiPolygon tiles using '{repair_strategy}' strategy...")
        
        if mp_df.empty:
            print("No MultiPolygons to repair!")
            return apartments_data, pd.DataFrame()
        
        repaired_count = 0
        failed_count = 0
        
        # Create a copy of the apartments_data to avoid modifying the original
        repaired_data = {apt_name: {'orientation': apt_data['orientation'], 
                                    'tiles': apt_data['tiles'].copy()} 
                        for apt_name, apt_data in apartments_data.items()}
        
        # Track repair results for reporting
        repair_results = []
        
        # Process each MultiPolygon
        for _, mp_info in mp_df.iterrows():
            apt_name = mp_info['apartment_name']
            room_id = mp_info['room_id']
            tile_idx = mp_info['tile_index']
            tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
            
            # Get the tile
            tile = repaired_data[apt_name]['tiles'][tile_idx]
            
            # Get the MultiPolygon
            mpoly = tile['polygon']
            original_area = mpoly.area
            
            # Apply the repair strategy
            try:
                repaired_poly = None
                
                if repair_strategy == 'largest_part':
                    # Keep only the largest part
                    parts = list(mpoly.geoms)
                    areas = [part.area for part in parts]
                    largest_part_idx = areas.index(max(areas))
                    repaired_poly = parts[largest_part_idx]
                    repair_desc = f"Kept largest part ({max(areas):.2f} units²)"
                    
                elif repair_strategy == 'convex_hull':
                    # Use the convex hull of the MultiPolygon
                    repaired_poly = mpoly.convex_hull
                    repair_desc = f"Created convex hull"
                    
                elif repair_strategy == 'buffer':
                    # Apply buffer(0) to attempt to fix
                    repaired_poly = mpoly.buffer(0)
                    if isinstance(repaired_poly, MultiPolygon):
                        # If still a MultiPolygon, fall back to largest part
                        parts = list(repaired_poly.geoms)
                        areas = [part.area for part in parts]
                        largest_part_idx = areas.index(max(areas))
                        repaired_poly = parts[largest_part_idx]
                        repair_desc = f"Buffer(0) then largest part ({max(areas):.2f} units²)"
                    else:
                        repair_desc = f"Buffer(0) successful"
                        
                elif repair_strategy == 'union':
                    # Try to union all parts
                    repaired_poly = unary_union(list(mpoly.geoms))
                    if isinstance(repaired_poly, MultiPolygon):
                        # If still a MultiPolygon, fall back to largest part
                        parts = list(repaired_poly.geoms)
                        areas = [part.area for part in parts]
                        largest_part_idx = areas.index(max(areas))
                        repaired_poly = parts[largest_part_idx]
                        repair_desc = f"Union then largest part ({max(areas):.2f} units²)"
                    else:
                        repair_desc = f"Union successful"
                
                # Ensure the repaired polygon is valid
                if repaired_poly and repaired_poly.is_valid:
                    # Update the tile with the repaired polygon
                    repaired_data[apt_name]['tiles'][tile_idx]['polygon'] = repaired_poly
                    
                    # Calculate area change percentage
                    new_area = repaired_poly.area
                    area_change_pct = ((new_area - original_area) / original_area) * 100
                    
                    # Store repair result
                    repair_results.append({
                        'tile_id': tile_id,
                        'strategy': repair_strategy,
                        'description': repair_desc,
                        'original_area': original_area,
                        'new_area': new_area,
                        'area_change_pct': area_change_pct,
                        'status': 'Success'
                    })
                    
                    repaired_count += 1
                else:
                    repair_results.append({
                        'tile_id': tile_id,
                        'strategy': repair_strategy,
                        'description': 'Failed - Invalid geometry after repair',
                        'original_area': original_area,
                        'new_area': None,
                        'area_change_pct': None,
                        'status': 'Failed'
                    })
                    failed_count += 1
                    
            except Exception as e:
                # Log the error and continue with the next tile
                repair_results.append({
                    'tile_id': tile_id,
                    'strategy': repair_strategy,
                    'description': f'Error: {str(e)}',
                    'original_area': original_area,
                    'new_area': None,
                    'area_change_pct': None,
                    'status': 'Failed'
                })
                failed_count += 1
        
        # Convert repair results to DataFrame
        repair_df = pd.DataFrame(repair_results)
        
        # Display repair results
        print(f"\n✅ Repair completed: {repaired_count} successful, {failed_count} failed")
        if not repair_df.empty:
            print("\n📋 Repair Results:")
            display_dataframe(repair_df, "Repair Results")
        
        return repaired_data, repair_df

    def split_multipolygons_into_individual_tiles(self, apartments_data, mp_df):
        """Split each MultiPolygon into separate individual tiles"""
        print("\n🔪 Splitting MultiPolygons into individual tiles...")
        
        if mp_df.empty:
            print("No MultiPolygons to split!")
            return apartments_data, pd.DataFrame()
        
        # Create a copy of the apartments_data to avoid modifying the original
        split_data = {apt_name: {'orientation': apt_data['orientation'], 
                                'tiles': apt_data['tiles'].copy()} 
                      for apt_name, apt_data in apartments_data.items()}
        
        # Track the original and split tiles
        split_results = []
        total_new_tiles = 0
        
        # Process each MultiPolygon
        for _, mp_info in mp_df.iterrows():
            apt_name = mp_info['apartment_name']
            room_id = mp_info['room_id']
            tile_idx = mp_info['tile_index']
            tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
            
            # Get the original tile
            original_tile = split_data[apt_name]['tiles'][tile_idx]
            orig_poly = original_tile['polygon']
            
            # Verify it's a MultiPolygon before processing
            if isinstance(orig_poly, MultiPolygon):
                # Get the parts
                parts = list(orig_poly.geoms)
                
                # Only process if there are multiple parts
                if len(parts) > 1:
                    # Create a new tile for each part
                    new_tiles = []
                    
                    # Store original tile index for reference
                    original_tile_idx = tile_idx
                    
                    # Keep the original tile as the first part
                    original_tile['polygon'] = parts[0]
                    original_tile['type'] = 'split' if original_tile['type'] == 'full' else 'split_cut'
                    original_tile['original_area'] = orig_poly.area
                    original_tile['part_area'] = parts[0].area
                    original_tile['part_percent'] = (parts[0].area / orig_poly.area) * 100
                    original_tile['is_split'] = True
                    original_tile['part_index'] = 0
                    original_tile['original_tile_index'] = original_tile_idx
                    
                    # Create new tile entries for the remaining parts
                    for part_idx, part in enumerate(parts[1:], 1):
                        # Create a new tile based on the original
                        new_tile = original_tile.copy()
                        new_tile['polygon'] = part
                        new_tile['type'] = 'split' if original_tile['type'] == 'full' else 'split_cut'
                        new_tile['part_area'] = part.area
                        new_tile['part_percent'] = (part.area / orig_poly.area) * 100
                        new_tile['is_split'] = True
                        new_tile['part_index'] = part_idx
                        new_tile['original_tile_index'] = original_tile_idx
                        
                        # Update the centroid if needed
                        if 'centroid' in new_tile:
                            if hasattr(part, 'centroid'):
                                new_tile['centroid'] = (part.centroid.x, part.centroid.y)
                        
                        new_tiles.append(new_tile)
                    
                    # Record the split result
                    split_results.append({
                        'tile_id': tile_id,
                        'original_parts': len(parts),
                        'largest_part_percent': (max(part.area for part in parts) / orig_poly.area) * 100,
                        'new_tiles': len(parts),
                        'area_preserved': 100.0  # We keep all the area
                    })
                    
                    # Add the new tiles to the apartment's tiles
                    split_data[apt_name]['tiles'].extend(new_tiles)
                    total_new_tiles += len(new_tiles)
        
        # Convert split results to DataFrame
        split_df = pd.DataFrame(split_results)
        
        # Display split results
        print(f"\n✅ Split completed: {len(split_df)} MultiPolygons split into {total_new_tiles} new tiles")
        if not split_df.empty:
            print("\n📋 Split Results:")
            display_dataframe(split_df, "Split Results")
        
        return split_data, split_df

    def verify_repair_results(self, apartments_data, repaired_data, mp_df):
        """Verify that all MultiPolygons have been properly repaired"""
        print("\n🔍 Verifying repair results...")
        
        # Count MultiPolygons in the original data
        original_mp_count = len(mp_df)
        
        # Count MultiPolygons in the repaired data
        repaired_mp_count = 0
        repaired_mp_details = []
        
        for apt_name, apt_data in repaired_data.items():
            for tile_idx, tile in enumerate(apt_data['tiles']):
                if isinstance(tile['polygon'], MultiPolygon):
                    repaired_mp_count += 1
                    
                    # Store details
                    repaired_mp_details.append({
                        'apartment_name': apt_name,
                        'room_id': tile['room_id'],
                        'tile_index': tile_idx,
                        'parts_count': len(list(tile['polygon'].geoms))
                    })
        
        # Display results
        print(f"Original MultiPolygons: {original_mp_count}")
        print(f"Remaining MultiPolygons after repair: {repaired_mp_count}")
        
        if repaired_mp_count == 0:
            print("\n✅ All MultiPolygons successfully converted to Polygons!")
        else:
            print("\n⚠️ Some MultiPolygons could not be repaired:")
            repaired_mp_df = pd.DataFrame(repaired_mp_details)
            display_dataframe(repaired_mp_df, "Remaining MultiPolygons")
        
        # Calculate success rate
        if original_mp_count > 0:
            success_rate = ((original_mp_count - repaired_mp_count) / original_mp_count) * 100
            print(f"\nRepair success rate: {success_rate:.2f}%")
        
        return repaired_mp_count

    def count_tiles_by_type_and_room(self, split_data, final_room_df):
        """Count tiles by type (regular, split) for each room and apartment"""
        print("\n📊 Counting tiles by type for each room...")
        
        # Prepare data structure
        tile_counts = []
        
        # Process each apartment
        for apt_name, apt_data in split_data.items():
            # Get rooms for this apartment
            apt_rooms = final_room_df[final_room_df['apartment_name'] == apt_name]
            
            # Initialize room counts
            room_counts = {}
            for _, room in apt_rooms.iterrows():
                room_counts[room['room_id']] = {
                    'apartment_name': apt_name,
                    'room_name': room['room_name'],
                    'regular_count': 0,
                    'split_count': 0,
                    'total_count': 0
                }
            
            # Count tiles
            for tile in apt_data['tiles']:
                room_id = tile['room_id']
                
                # Skip if room not found
                if room_id not in room_counts:
                    continue
                
                # Check if this is a split tile
                is_split = 'is_split' in tile and tile['is_split']
                
                if is_split:
                    room_counts[room_id]['split_count'] += 1
                else:
                    room_counts[room_id]['regular_count'] += 1
                
                room_counts[room_id]['total_count'] += 1
            
            # Add to results
            for room_id, counts in room_counts.items():
                tile_counts.append(counts)
        
        # Convert to DataFrame
        counts_df = pd.DataFrame(tile_counts)
        
        # Calculate percentages
        counts_df['split_percent'] = (counts_df['split_count'] / counts_df['total_count'] * 100).round(1)
        
        # Sort by apartment and room
        counts_df = counts_df.sort_values(['apartment_name', 'room_name'])
        
        # Display results
        print("\n📋 Tile Counts by Room:")
        display_dataframe(counts_df, "Tile Counts")
        
        # Summary
        total_regular = counts_df['regular_count'].sum()
        total_split = counts_df['split_count'].sum()
        total_tiles = counts_df['total_count'].sum()
        
        print(f"\nTotal Regular Tiles: {total_regular}")
        print(f"Total Split Tiles: {total_split}")
        print(f"Total Tiles: {total_tiles}")
        print(f"Percentage of Split Tiles: {(total_split / total_tiles * 100):.1f}%")
        
        return counts_df

    def analyze_tile_sizes(self, apartments_data, final_room_df):
        """Analyze tile sizes and identify small tiles that might need attention"""
        print("\n🔍 Analyzing tile sizes...")
        
        # Prepare data structure to collect all tile information
        all_tiles = []
        
        # Process each apartment
        for apt_name, apt_data in apartments_data.items():
            # Get apartment orientation
            apt_orientation = apt_data['orientation']
            
            # Process each tile
            for tile_idx, tile in enumerate(apt_data['tiles']):
                room_id = tile['room_id']
                
                # Get room name if available
                room_name = f"Room {room_id}"
                for _, room in final_room_df.iterrows():
                    if room['room_id'] == room_id:
                        room_name = room['room_name']
                        break
                
                # Get tile attributes
                polygon = tile['polygon']
                tile_type = tile.get('type', 'unknown')
                is_split = tile.get('is_split', False)
                part_index = tile.get('part_index', None)
                
                # Calculate area
                area = polygon.area
                
                # Calculate dimensions
                try:
                    minx, miny, maxx, maxy = polygon.bounds
                    width = maxx - minx
                    height = maxy - miny
                    perimeter = polygon.length
                    
                    # Calculate compactness (normalized ratio of area to perimeter)
                    # This helps identify stretched/irregular tiles
                    compactness = 4 * math.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                    
                    # Create a unique ID for the tile
                    if is_split:
                        original_tile_idx = tile.get('original_tile_index', tile_idx)
                        tile_id = f"{apt_name}-R{room_id}-T{original_tile_idx}-P{part_index}"
                    else:
                        tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
                    
                    # Store tile data
                    tile_data = {
                        'tile_id': tile_id,
                        'apartment': apt_name,
                        'room_id': room_id,
                        'room_name': room_name,
                        'tile_index': tile_idx,
                        'area': area,
                        'width': width,
                        'height': height,
                        'perimeter': perimeter,
                        'compactness': compactness,
                        'type': tile_type,
                        'is_split': is_split,
                        'part_index': part_index,
                        'orientation': apt_orientation,
                        'centroid_x': polygon.centroid.x,
                        'centroid_y': polygon.centroid.y
                    }
                    
                    all_tiles.append(tile_data)
                    
                except Exception as e:
                    print(f"❌ Error processing tile {apt_name}-R{room_id}-T{tile_idx}: {e}")
        
        # Convert to DataFrame for analysis
        tiles_df = pd.DataFrame(all_tiles)
        
        # Calculate basic statistics
        total_tiles = len(tiles_df)
        total_area = tiles_df['area'].sum()
        avg_area = tiles_df['area'].mean()
        min_area = tiles_df['area'].min()
        max_area = tiles_df['area'].max()
        
        # Display basic statistics
        print(f"\n📊 Tile Statistics:")
        print(f"Total number of tiles: {total_tiles}")
        print(f"Total tile area: {total_area:.2f} square units")
        print(f"Average tile area: {avg_area:.2f} square units")
        print(f"Smallest tile area: {min_area:.2f} square units")
        print(f"Largest tile area: {max_area:.2f} square units")
        
        # Sort by area for easy reference
        tiles_df = tiles_df.sort_values('area')
        
        return tiles_df

    def identify_small_tiles(self, tiles_df, area_threshold_percent=5.0):
        """Identify tiles that are significantly smaller than the average"""
        print(f"\n🔍 Identifying small tiles (smaller than {area_threshold_percent}% of average area)...")
        
        # Calculate average tile area (excluding split tiles)
        avg_area = tiles_df[~tiles_df['is_split']]['area'].mean()
        
        # Calculate area threshold
        area_threshold = avg_area * (area_threshold_percent / 100.0)
        print(f"Average regular tile area: {avg_area:.2f} square units")
        print(f"Area threshold: {area_threshold:.2f} square units")
        
        # Identify small tiles
        small_tiles = tiles_df[tiles_df['area'] < area_threshold].copy()
        small_tiles['percent_of_avg'] = (small_tiles['area'] / avg_area) * 100
        
        # Sort by area (smallest first)
        small_tiles = small_tiles.sort_values('area')
        
        # Display results
        if not small_tiles.empty:
            small_count = len(small_tiles)
            small_percent = (small_count / len(tiles_df)) * 100
            print(f"\n⚠️ Found {small_count} small tiles ({small_percent:.2f}% of total)")
            
            # Display small tiles table
            print("\n📋 Small Tiles Detail (sorted by area):")
            display_cols = ['tile_id', 'apartment', 'room_name', 'area', 'percent_of_avg', 'type', 'is_split']
            display_dataframe(small_tiles[display_cols].head(20), "Small Tiles")
            
            if len(small_tiles) > 20:
                print(f"(Showing top 20 of {len(small_tiles)} small tiles)")
        else:
            print("\n✅ No small tiles found below the threshold!")
        
        return small_tiles, area_threshold

    def identify_small_cut_tiles(self, tiles_df, final_room_df, has_pattern=False, size_threshold=10):
        """Identify cut tiles with dimension less than the specified threshold"""
        print(f"\n🔍 Identifying cut tiles with dimension < {size_threshold}mm...")
        
        # Find small cut tiles based on pattern mode
        if has_pattern:
            # With pattern: check cut_x and cut_y separately
            small_x_tiles = tiles_df[
                (tiles_df['classification'] == 'cut_x') & 
                (tiles_df['cut_side'] < size_threshold)
            ].copy()
            
            small_y_tiles = tiles_df[
                (tiles_df['classification'] == 'cut_y') & 
                (tiles_df['cut_side'] < size_threshold)
            ].copy()
            
            # Combine small x and y tiles
            small_tiles_df = pd.concat([small_x_tiles, small_y_tiles])
            
        else:
            # No pattern: check all_cut tiles
            small_tiles_df = tiles_df[
                (tiles_df['classification'] == 'all_cut') & 
                (tiles_df['cut_side'] < size_threshold)
            ].copy()
        
        # Count small tiles
        small_tile_count = len(small_tiles_df)
        total_cut_count = len(tiles_df[tiles_df['classification'].isin(['cut_x', 'cut_y', 'all_cut'])])
        
        if small_tile_count > 0:
            print(f"✅ Found {small_tile_count} cut tiles smaller than {size_threshold}mm")
            print(f"   This represents {small_tile_count/total_cut_count*100:.1f}% of all cut tiles")
            
            # Group by apartment and room
            location_summary = small_tiles_df.groupby(['apartment_name', 'room_name']).size().reset_index(name='count')
            print("\n📊 Small Tile Distribution by Location:")
            for _, row in location_summary.iterrows():
                print(f"   {row['apartment_name']} - {row['room_name']}: {row['count']} small tiles")
        else:
            print(f"✅ No cut tiles smaller than {size_threshold}mm found")
        
        return small_tiles_df, small_tile_count

        # Add this method to TileProcessor class

    def identify_small_tiles_combined(self, tile_classification_results, tile_analysis_results, final_room_df):
        """Identify small tiles: irregular by area (<1%) and cut tiles by dimension (<10mm)"""
        
        # Get required data from classification results
        tiles_df_data = tile_classification_results['tiles_df']
        
        # Convert to DataFrame if it's not already
        if isinstance(tiles_df_data, list):
            tiles_df = pd.DataFrame(tiles_df_data)
        else:
            tiles_df = tiles_df_data
        
        has_pattern = tile_classification_results['has_pattern']
        
        # Get small irregular tiles from Step 4
        small_irregular_tiles_data = tile_analysis_results.get('small_irregular_tiles', [])
        
        # Convert to DataFrame if needed
        if isinstance(small_irregular_tiles_data, list):
            small_irregular_tiles = pd.DataFrame(small_irregular_tiles_data) if small_irregular_tiles_data else pd.DataFrame()
        else:
            small_irregular_tiles = small_irregular_tiles_data
        
        area_threshold = tile_analysis_results.get('area_threshold', 0)
        
        print("\n🔍 Identifying small tiles with specific criteria:")
        print("  - IRREGULAR tiles: Area < 1% of average")
        print("  - CUT tiles (cut_x, cut_y, all_cut): Cut dimension < 10mm")
        
        # Fixed threshold of 10mm for dimension-based detection
        size_threshold = 10.0
        
        # Find small cut tiles based on dimension (<10mm)
        small_cut_tiles_dimension, small_cut_count = self.identify_small_cut_tiles(
            tiles_df, final_room_df, has_pattern, size_threshold
        )
        
        # Initialize all_small_tiles
        all_small_tiles = pd.DataFrame()
        
        # Process small cut tiles
        if not small_cut_tiles_dimension.empty:
            # Add required columns if they don't exist
            small_cut_tiles_dimension['small_type'] = 'cut_dimension_based'
            small_cut_tiles_dimension['small_criteria'] = 'dimension < 10mm'
            all_small_tiles = pd.concat([all_small_tiles, small_cut_tiles_dimension])
        
        # Process small irregular tiles from Step 4
        if not small_irregular_tiles.empty:
            # Ensure the columns exist
            if 'small_type' not in small_irregular_tiles.columns:
                small_irregular_tiles['small_type'] = 'irregular_area_based'
            if 'small_criteria' not in small_irregular_tiles.columns:
                small_irregular_tiles['small_criteria'] = 'area < 1%'
            
            # Only concatenate if we have matching columns
            if 'tile_index' in small_irregular_tiles.columns and 'apartment_name' in small_irregular_tiles.columns:
                all_small_tiles = pd.concat([all_small_tiles, small_irregular_tiles], ignore_index=True)
        
        # Remove duplicates if any exist
        if not all_small_tiles.empty:
            # Create unique identifier only if columns exist
            if 'tile_index' in all_small_tiles.columns and 'apartment_name' in all_small_tiles.columns:
                all_small_tiles['unique_id'] = all_small_tiles['apartment_name'].astype(str) + '_' + all_small_tiles['tile_index'].astype(str)
                all_small_tiles = all_small_tiles.drop_duplicates(subset=['unique_id'], keep='first')
                all_small_tiles = all_small_tiles.drop(columns=['unique_id'])
        
        # Calculate statistics safely
        total_small_tiles = len(all_small_tiles)
        small_irregular_count = 0
        small_cut_count = 0
        
        if not all_small_tiles.empty and 'small_type' in all_small_tiles.columns:
            small_irregular_count = len(all_small_tiles[all_small_tiles['small_type'] == 'irregular_area_based'])
            small_cut_count = len(all_small_tiles[all_small_tiles['small_type'] == 'cut_dimension_based'])
        
        return all_small_tiles, total_small_tiles, small_irregular_count, small_cut_count, size_threshold, area_threshold

    def exclude_small_tiles_from_classification(self, tile_classification_results, tiles_df, 
                                          small_cut_tiles_dimension, small_irregular_tiles, 
                                          has_pattern):
        """Exclude small tiles from tile classification results"""
        
        # Ensure tiles_df is a DataFrame
        if isinstance(tiles_df, list):
            tiles_df = pd.DataFrame(tiles_df)
        
        # Ensure small DataFrames are DataFrames
        if isinstance(small_cut_tiles_dimension, list):
            small_cut_tiles_dimension = pd.DataFrame(small_cut_tiles_dimension) if small_cut_tiles_dimension else pd.DataFrame()
        if isinstance(small_irregular_tiles, list):
            small_irregular_tiles = pd.DataFrame(small_irregular_tiles) if small_irregular_tiles else pd.DataFrame()
        
        # Get indices to exclude based on the tiles_df index
        exclude_indices = []
        
        # For cut tiles, match based on multiple criteria
        if not small_cut_tiles_dimension.empty:
            for _, small_tile in small_cut_tiles_dimension.iterrows():
                # Find matching tiles in tiles_df
                mask = (
                    (tiles_df['apartment_name'] == small_tile['apartment_name']) &
                    (tiles_df['room_name'] == small_tile['room_name']) &
                    (tiles_df['classification'] == small_tile['classification']) &
                    (tiles_df['tile_index'] == small_tile['tile_index'])
                )
                matching_indices = tiles_df[mask].index.tolist()
                exclude_indices.extend(matching_indices)
        
        # For irregular tiles from Step 4
        if not small_irregular_tiles.empty and 'tile_index' in small_irregular_tiles.columns:
            for _, small_tile in small_irregular_tiles.iterrows():
                if 'apartment_name' in small_tile and 'tile_index' in small_tile:
                    mask = (
                        (tiles_df['apartment_name'] == small_tile['apartment_name']) &
                        (tiles_df['tile_index'] == small_tile['tile_index'])
                    )
                    matching_indices = tiles_df[mask].index.tolist()
                    exclude_indices.extend(matching_indices)
        
        # Remove duplicates
        exclude_indices = list(set(exclude_indices))
        
        if exclude_indices:
            # Create a new tiles DataFrame excluding small tiles
            updated_tiles_df = tiles_df.drop(exclude_indices)
            
            # Update the classification result dictionaries
            tile_classification_results['tiles_df'] = updated_tiles_df.to_dict('records')
            
            # Count what we're removing
            removed_counts = {'irregular': 0, 'cut_x': 0, 'cut_y': 0, 'all_cut': 0}
            for idx in exclude_indices:
                if idx in tiles_df.index:
                    classification = tiles_df.loc[idx, 'classification']
                    if classification in removed_counts:
                        removed_counts[classification] += 1
            
            # Update other DataFrames based on pattern mode
            if has_pattern:
                # Update cut_x and cut_y DataFrames
                if 'cut_x_tiles' in tile_classification_results:
                    cut_x_tiles = pd.DataFrame(tile_classification_results['cut_x_tiles'])
                    if not cut_x_tiles.empty:
                        cut_x_tiles = cut_x_tiles[~cut_x_tiles.index.isin(exclude_indices)]
                        tile_classification_results['cut_x_tiles'] = cut_x_tiles.to_dict('records')
                
                if 'cut_y_tiles' in tile_classification_results:
                    cut_y_tiles = pd.DataFrame(tile_classification_results['cut_y_tiles'])
                    if not cut_y_tiles.empty:
                        cut_y_tiles = cut_y_tiles[~cut_y_tiles.index.isin(exclude_indices)]
                        tile_classification_results['cut_y_tiles'] = cut_y_tiles.to_dict('records')
                
                tile_classification_results['stats']['cut_x_tiles'] -= removed_counts['cut_x']
                tile_classification_results['stats']['cut_y_tiles'] -= removed_counts['cut_y']
            else:
                # Update all_cut DataFrame
                if 'all_cut_tiles' in tile_classification_results:
                    all_cut_tiles = pd.DataFrame(tile_classification_results['all_cut_tiles'])
                    if not all_cut_tiles.empty:
                        all_cut_tiles = all_cut_tiles[~all_cut_tiles.index.isin(exclude_indices)]
                        tile_classification_results['all_cut_tiles'] = all_cut_tiles.to_dict('records')
                
                tile_classification_results['stats']['all_cut_tiles'] -= removed_counts['all_cut']
            
            # Update irregular tiles
            if 'irregular_tiles' in tile_classification_results:
                irregular_tiles = pd.DataFrame(tile_classification_results['irregular_tiles'])
                if not irregular_tiles.empty:
                    irregular_tiles = irregular_tiles[~irregular_tiles.index.isin(exclude_indices)]
                    tile_classification_results['irregular_tiles'] = irregular_tiles.to_dict('records')
            
            # Update statistics
            tile_classification_results['stats']['total_tiles'] -= len(exclude_indices)
            tile_classification_results['stats']['irregular_tiles'] -= removed_counts['irregular']
            
            return len(exclude_indices), removed_counts, updated_tiles_df
        
        return 0, {}, tiles_df