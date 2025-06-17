import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import random
from shapely.geometry import Polygon, MultiPolygon
import numpy as np
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.patches as patches
import io
import base64
import pandas as pd

from processors.utility_functions import display_dataframe

class VisualizationProcessor:
    def __init__(self):
        self.colors = {}
        self.apartment_names = {}

    def plot_room_boundaries(self, rooms, start_points=None):
        plt.figure(figsize=(12, 12))
        for room in rooms:
            x, y = room.exterior.xy
            plt.plot(x, y, color='blue', linewidth=1.5)
        if start_points:
            for sp in start_points:
                cx, cy = sp['centroid']
                plt.plot(cx, cy, 'ro', markersize=8)
                plt.text(cx, cy, 'SP', fontsize=8, ha='center', color='red')
        plt.title("📐 Room Boundaries with Tile Start Points")
        plt.grid(True)
        
        # Convert plot to base64 string
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def plot_clusters(self, clusters_df, use_final_names=False):
        plt.figure(figsize=(14, 14))
        unique_clusters = clusters_df['apartment_cluster'].unique()

        if use_final_names and 'apartment_name' in clusters_df.columns:
            apartment_names = clusters_df.groupby('apartment_cluster')['apartment_name'].first().to_dict()
            self.apartment_names.update(apartment_names)
        else:
            apartment_names = {cluster_id: f"Apartment {cluster_id+1}" for cluster_id in unique_clusters}

        for cluster_id in unique_clusters:
            cluster_rooms = clusters_df[clusters_df['apartment_cluster'] == cluster_id]
            color = self.get_color(cluster_id)
            apt_name = self.apartment_names.get(cluster_id, apartment_names.get(cluster_id, f"Apartment {cluster_id+1}"))
            for idx, row in cluster_rooms.iterrows():
                polygon = row['polygon']
                x, y = polygon.exterior.xy
                plt.fill(x, y, alpha=0.6, label=apt_name if idx == cluster_rooms.index[0] else "", color=color)
                plt.text(row['centroid_x'], row['centroid_y'], row['room_name'], fontsize=8, ha='center', color='black')
        plt.title("🏢 Apartment Clusters with Room Names")
        plt.legend()
        plt.grid(True)
        
        # Convert plot to base64 string
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def get_color(self, cluster_id):
        if cluster_id not in self.colors:
            self.colors[cluster_id] = (random.random(), random.random(), random.random())
        return self.colors[cluster_id]

    def create_grout_outline_visualization(self, apartments_data, room_df=None):
        """Creates visualization with white grout lines between tiles"""
        print("\n🎨 Creating visualization with white grout lines...")
        
        plt.figure(figsize=(16, 16))
        
        # Generate apartment colors
        apartment_colors = {apt_name: np.random.rand(3,) for apt_name in apartments_data.keys()}
        
        # Plot room outlines if provided
        if room_df is not None:
            for _, room in room_df.iterrows():
                room_poly = room['polygon']
                x, y = room_poly.exterior.xy
                plt.plot(x, y, color='black', linewidth=1.5)
                plt.text(room['centroid_x'], room['centroid_y'],
                         f"{room['apartment_name']}-{room['room_name']}",
                         fontsize=10, ha='center', va='center')
        
        # First, plot layout tiles (with grout) in white to create grout lines
        for apt_name, apt_data in apartments_data.items():
            for tile in apt_data['tiles']:
                layout_poly = tile.get('layout_polygon', tile['polygon'])
                if isinstance(layout_poly, Polygon) and layout_poly.is_valid and not layout_poly.is_empty:
                    x, y = layout_poly.exterior.xy
                    plt.fill(x, y, color='white', edgecolor='none')
                elif isinstance(layout_poly, MultiPolygon):
                    for part in layout_poly.geoms:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color='white', edgecolor='none')
        
        # Then, plot actual tiles (factory size) with apartment colors
        rendered_tiles = 0
        for apt_name, apt_data in apartments_data.items():
            color = apartment_colors[apt_name]
            
            for tile in apt_data['tiles']:
                poly = tile['polygon']
                if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                    x, y = poly.exterior.xy
                    plt.fill(x, y, color=color, edgecolor='black', linewidth=0.2)
                    rendered_tiles += 1
                elif isinstance(poly, MultiPolygon):
                    for part in poly.geoms:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color=color, edgecolor='black', linewidth=0.2)
                    rendered_tiles += 1
        
        total_tiles = sum(len(apt_data['tiles']) for apt_name, apt_data in apartments_data.items())
        print(f"Total tiles: {total_tiles}, Rendered tiles: {rendered_tiles}")
        
        plt.axis('equal')
        plt.grid(False)
        plt.title(f"Apartment Tile Layout with Explicit Grout Lines")
        
        # Add legend
        for apt_name, color in apartment_colors.items():
            plt.plot([], [], color=color, alpha=0.5, linewidth=10, label=apt_name)
        plt.legend()
        
        plt.tight_layout()
        
        # Convert plot to base64 string
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        
        return base64.b64encode(buf.read()).decode('utf-8')

    def visualize_classification(self, tiles_df, final_room_df, has_pattern=False, with_grout=True):
        """Optimized visualization of classified tiles"""
        print(f"\n🎨 Visualizing classified tiles...")
        
        plt.figure(figsize=(16, 16))
        
        # Plot room outlines
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.8)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=10, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Define colors for different classifications
        colors = {
            'full': 'green',
            'irregular': 'blue',
            'cut_x': 'orange',
            'cut_y': 'red',
            'all_cut': 'purple',
            'unknown': 'gray'
        }
        
        # Track counts for legend
        classification_counts = {cls: 0 for cls in colors}
        classification_counts['total'] = 0
        
        # Plot each tile with its classification color
        for _, tile in tiles_df.iterrows():
            classification = tile['classification']
            color = colors.get(classification, 'gray')
            poly = tile['polygon']
            
            try:
                if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                    x, y = poly.exterior.xy
                    plt.fill(x, y, color=color, alpha=0.7, edgecolor='black', linewidth=0.5)
                    classification_counts[classification] = classification_counts.get(classification, 0) + 1
                    classification_counts['total'] += 1
                elif isinstance(poly, MultiPolygon):
                    for part in poly.geoms:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color=color, alpha=0.7, edgecolor='black', linewidth=0.5)
                    classification_counts[classification] = classification_counts.get(classification, 0) + 1
                    classification_counts['total'] += 1
            except Exception as e:
                print(f"Error plotting tile: {e}")
        
        # Add legend with counts
        legend_elements = []
        for cls, color in colors.items():
            count = classification_counts.get(cls, 0)
            if count > 0:
                from matplotlib.patches import Patch
                legend_elements.append(
                    Patch(facecolor=color, alpha=0.7, edgecolor='black', 
                          label=f"{cls.capitalize()} ({count}, {count/classification_counts['total']*100:.1f}%)")
                )
        
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.title(f"Tiles Classified by Type with {'Pattern' if has_pattern else 'No Pattern'} {' (with Grout Lines)' if with_grout else ''}")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        return classification_counts

    def visualize_multipolygons_in_detail(self, apartments_data, mp_df, final_room_df):
        """Create a detailed visualization of MultiPolygon tiles only"""
        if mp_df.empty:
            print("\n✅ No MultiPolygons to visualize!")
            return None
        
        print("\n🔍 Creating detailed visualization of MultiPolygon tiles...")
        
        # Create a figure
        plt.figure(figsize=(16, 16))
        
        # Plot room boundaries
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.5)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=9, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Define fixed colors for each apartment
        apt_colors = {}
        unique_apts = mp_df['apartment_name'].unique()
        color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for i, apt in enumerate(unique_apts):
            apt_colors[apt] = color_list[i % len(color_list)]
        
        # For each part, use a different shade of the apartment color
        part_colors = {}
        for apt in unique_apts:
            base_color = apt_colors[apt]
            # Create a lighter version for alternating parts
            light_color = f"#{int(base_color[1:3], 16):02x}{int(base_color[3:5], 16):02x}{min(255, int(base_color[5:7], 16) + 80):02x}"
            part_colors[apt] = [base_color, light_color]
        
        # Plot each MultiPolygon with different colors for each part
        for _, mp_info in mp_df.iterrows():
            apt_name = mp_info['apartment_name']
            room_id = mp_info['room_id']
            tile_idx = mp_info['tile_index']
            
            # Create a tile ID
            tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
            
            # Get the tile from apartments_data
            tile = apartments_data[apt_name]['tiles'][tile_idx]
            
            # Get the polygon
            mpoly = tile['polygon']
            
            # Plot each part of the MultiPolygon with a different color
            parts = list(mpoly.geoms)
            for part_idx, part in enumerate(parts):
                # Choose color based on part index (modulo for safety)
                color = part_colors.get(apt_name, ['#2ca02c', '#98df8a'])[part_idx % 2]
                
                # Plot the part
                if part.is_valid and not part.is_empty:
                    x, y = part.exterior.xy
                    plt.fill(x, y, color=color, alpha=0.7, edgecolor='black', linewidth=0.5)
                    
                    # Add part label
                    part_centroid = part.centroid
                    plt.text(part_centroid.x, part_centroid.y, 
                             f"P{part_idx+1}",
                             fontsize=8, ha='center', va='center')
            
            # Add numbered tile label at the centroid
            if parts:
                # Use the centroid of the MultiPolygon
                centroid = mpoly.centroid
                plt.text(centroid.x, centroid.y,  
                         f"{tile_id}\n({len(parts)} parts)",
                         fontsize=9, ha='center', va='center',
                         bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
                
                # Add a marker at the centroid for visibility
                plt.plot(centroid.x, centroid.y, 'ro', markersize=5)
        
        # Add legend for apartments
        for apt_name, color in apt_colors.items():
            plt.plot([], [], color=color, alpha=0.7, linewidth=10, label=apt_name)
        plt.legend()
        
        plt.title(f"MultiPolygon Tiles Visualization ({len(mp_df)} tiles)")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def visualize_all_tiles_highlighting_multipolygons(self, apartments_data, mp_df, final_room_df):
        """Create a visualization of ALL tiles with MultiPolygons highlighted"""
        print("\n🔍 Creating visualization of all tiles with MultiPolygons highlighted...")
        
        # Create a figure
        plt.figure(figsize=(18, 18))
        
        # Plot room boundaries
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.8)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=10, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Create a set of MultiPolygon tile indexes for quick lookup
        mp_tiles = set()
        for _, row in mp_df.iterrows():
            mp_tiles.add((row['apartment_name'], row['tile_index']))
        
        # Draw all tiles
        for apt_name, apt_data in apartments_data.items():
            # Get a color for this apartment
            apt_color = plt.cm.tab10(hash(apt_name) % 10)
            
            for tile_idx, tile in enumerate(apt_data['tiles']):
                poly = tile['polygon']
                is_multipolygon = (apt_name, tile_idx) in mp_tiles
                
                # Different styling for MultiPolygons vs regular polygons
                if is_multipolygon:
                    # For MultiPolygons, highlight each part
                    parts = list(poly.geoms)
                    for part in parts:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color='red', alpha=0.7, edgecolor='black', linewidth=0.5)
                else:
                    # For regular Polygons, use apartment color
                    if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                        x, y = poly.exterior.xy
                        plt.fill(x, y, color=apt_color, alpha=0.3, edgecolor='gray', linewidth=0.1)
        
        # Add markers for each MultiPolygon with numbers
        for i, (_, row) in enumerate(mp_df.iterrows(), 1):
            apt_name = row['apartment_name']
            tile_idx = row['tile_index']
            centroid_x = row.get('centroid_x')
            centroid_y = row.get('centroid_y')
            
            if centroid_x is not None and centroid_y is not None:
                plt.plot(centroid_x, centroid_y, 'ro', markersize=8)
                plt.text(centroid_x, centroid_y, str(i), 
                        fontsize=10, ha='center', va='center', color='white',
                        bbox=dict(facecolor='red', alpha=0.8, boxstyle='circle'))
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', alpha=0.7, edgecolor='black', label='MultiPolygon Tiles'),
            Patch(facecolor='lightgray', alpha=0.3, edgecolor='gray', label='Regular Tiles')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.title(f"All Tiles with MultiPolygons Highlighted in Red ({len(mp_df)} MultiPolygons)")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def visualize_split_results(self, apartments_data, split_data, mp_df, final_room_df):
        """Create a visualization comparing original MultiPolygons with split tiles"""
        if mp_df.empty:
            print("\n✅ No MultiPolygons to visualize split results!")
            return None
        
        print("\n🔍 Creating before/after visualization of split MultiPolygons...")
        
        # Choose a subset of MultiPolygons to visualize if there are too many
        sample_size = min(4, len(mp_df))
        if len(mp_df) > sample_size:
            print(f"Too many MultiPolygons to visualize all. Showing {sample_size} random samples.")
            sample_df = mp_df.sample(sample_size, random_state=42)
        else:
            sample_df = mp_df
        
        # Calculate the grid size for subplots
        n_rows = max(1, (sample_size + 1) // 2)
        n_cols = min(2, sample_size)
        
        # Create a figure with subplots
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 8 * n_rows))
        if n_rows == 1 and n_cols == 1:
            axes = np.array([axes])
        axes = axes.flatten()
        
        # Process each MultiPolygon
        for i, (_, mp_info) in enumerate(sample_df.iterrows()):
            if i >= len(axes):
                break
                
            apt_name = mp_info['apartment_name']
            room_id = mp_info['room_id']
            tile_idx = mp_info['tile_index']
            tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
            
            # Set up subplot
            ax = axes[i]
            
            # Get the original room polygon for context
            room_poly = None
            for _, room in final_room_df.iterrows():
                if room['room_id'] == room_id:
                    room_poly = room['polygon']
                    break
            
            if room_poly:
                x, y = room_poly.exterior.xy
                ax.plot(x, y, color='black', linewidth=1, alpha=0.3)
            
            # Get the original MultiPolygon
            orig_tile = apartments_data[apt_name]['tiles'][tile_idx]
            orig_mpoly = orig_tile['polygon']
            
            # Check if it's a MultiPolygon and plot its parts
            if isinstance(orig_mpoly, MultiPolygon):
                # Plot original MultiPolygon parts in red
                parts = list(orig_mpoly.geoms)
                for part_idx, part in enumerate(parts):
                    if part.is_valid and not part.is_empty:
                        x, y = part.exterior.xy
                        ax.fill(x, y, color='red', alpha=0.3, edgecolor='black', linewidth=0.5)
                        ax.text(part.centroid.x, part.centroid.y, f"Original P{part_idx+1}", 
                               fontsize=8, ha='center', va='center', color='darkred')
            else:
                # Handle case where the original is already a Polygon
                if orig_mpoly.is_valid and not orig_mpoly.is_empty:
                    x, y = orig_mpoly.exterior.xy
                    ax.fill(x, y, color='red', alpha=0.3, edgecolor='black', linewidth=0.5)
                    ax.text(orig_mpoly.centroid.x, orig_mpoly.centroid.y, "Original", 
                           fontsize=8, ha='center', va='center', color='darkred')
            
            # Find the split tiles in the new data
            found_parts = 0
            for new_tile in split_data[apt_name]['tiles']:
                # Check if this is a split tile from the original
                if 'is_split' in new_tile and new_tile['is_split'] and new_tile['room_id'] == room_id:
                    # Check if this is from the original tile we're looking at
                    if 'original_tile_index' in new_tile and new_tile['original_tile_index'] == tile_idx:
                        part_poly = new_tile['polygon']
                        part_idx = new_tile['part_index']
                        
                        if isinstance(part_poly, Polygon) and part_poly.is_valid and not part_poly.is_empty:
                            x, y = part_poly.exterior.xy
                            ax.fill(x, y, color='blue', alpha=0.5, edgecolor='black', linewidth=1)
                            ax.text(part_poly.centroid.x, part_poly.centroid.y, f"Split T{part_idx+1}", 
                                   fontsize=8, ha='center', va='center', color='white')
                            found_parts += 1
            
            # Set title and legend
            ax.set_title(f"Tile: {tile_id} - {found_parts} Split Tiles")
            ax.set_aspect('equal')
            ax.grid(False)
            
            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='red', alpha=0.3, edgecolor='black', label='Original MultiPolygon'),
                Patch(facecolor='blue', alpha=0.5, edgecolor='black', label='Split Tiles')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        plt.suptitle("Before (Red) and After (Blue) MultiPolygon Splitting", y=1.02, fontsize=16)
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def visualize_all_tiles_after_splitting(self, split_data, mp_df, final_room_df):
        """Create a visualization of ALL tiles after splitting MultiPolygons"""
        print("\n🔍 Creating visualization of all tiles after splitting MultiPolygons...")
        
        # Create a figure
        plt.figure(figsize=(18, 18))
        
        # Plot room boundaries
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.8)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=10, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Create a set of original MultiPolygon tile indexes for reference
        mp_tiles = set()
        for _, row in mp_df.iterrows():
            mp_tiles.add((row['apartment_name'], row['tile_index']))
        
        # Draw all tiles
        split_count = 0
        regular_count = 0
        
        for apt_name, apt_data in split_data.items():
            # Get a color for this apartment
            apt_color = plt.cm.tab10(hash(apt_name) % 10)
            
            for tile in apt_data['tiles']:
                poly = tile['polygon']
                
                # Check if this is a split tile
                is_split = 'is_split' in tile and tile['is_split']
                
                # Different styling for split vs regular tiles
                if is_split:
                    split_count += 1
                    # For split tiles, use a bright blue color
                    if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                        x, y = poly.exterior.xy
                        plt.fill(x, y, color='blue', alpha=0.7, edgecolor='black', linewidth=0.5)
                        
                        # Add a small label for the part index if it exists
                        if 'part_index' in tile:
                            plt.text(poly.centroid.x, poly.centroid.y, 
                                     f"P{tile['part_index']}", 
                                     fontsize=7, ha='center', va='center', color='white',
                                     bbox=dict(facecolor='blue', alpha=0.5, boxstyle='round,pad=0.1'))
                else:
                    regular_count += 1
                    # For regular tiles, use apartment color
                    if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                        x, y = poly.exterior.xy
                        plt.fill(x, y, color=apt_color, alpha=0.3, edgecolor='gray', linewidth=0.1)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='blue', alpha=0.7, edgecolor='black', label='Split Tiles'),
            Patch(facecolor='lightgray', alpha=0.3, edgecolor='gray', label='Regular Tiles')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.title(f"All Tiles After Splitting MultiPolygons ({split_count} split tiles, {regular_count} regular tiles)")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        base64_plot = base64.b64encode(buf.read()).decode('utf-8')
        
        return split_count, regular_count

    def visualize_all_tiles_highlighting_small(self, apartments_data, small_tiles, final_room_df, area_threshold):
        """Create a visualization of all tiles with small tiles highlighted"""
        print("\n🔍 Creating visualization with small tiles highlighted...")
        
        # Create a figure
        plt.figure(figsize=(18, 18))
        
        # Plot room boundaries
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.8)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=10, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Create a set of small tile IDs for quick lookup
        small_tile_ids = set(small_tiles['tile_id'])
        
        # Draw all tiles
        small_count = 0
        regular_count = 0
        
        for apt_name, apt_data in apartments_data.items():
            # Get a color for this apartment
            apt_color = plt.cm.tab10(hash(apt_name) % 10)
            
            for tile_idx, tile in enumerate(apt_data['tiles']):
                poly = tile['polygon']
                room_id = tile['room_id']
                
                # Create tile ID
                is_split = 'is_split' in tile and tile['is_split']
                if is_split:
                    part_index = tile.get('part_index', 0)
                    original_tile_idx = tile.get('original_tile_index', tile_idx)
                    tile_id = f"{apt_name}-R{room_id}-T{original_tile_idx}-P{part_index}"
                else:
                    tile_id = f"{apt_name}-R{room_id}-T{tile_idx}"
                
                # Check if this is a small tile
                area = poly.area
                is_small = area < area_threshold or tile_id in small_tile_ids
                
                # Different styling for small vs regular tiles
                if is_small:
                    small_count += 1
                    # For small tiles, use a red color with high visibility
                    if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                        x, y = poly.exterior.xy
                        plt.fill(x, y, color='red', alpha=0.7, edgecolor='black', linewidth=0.5)
                        
                        # Add a small label with area information
                        plt.text(poly.centroid.x, poly.centroid.y, 
                                 f"A: {area:.0f}", 
                                 fontsize=6, ha='center', va='center', color='white',
                                 bbox=dict(facecolor='red', alpha=0.5, boxstyle='round,pad=0.1'))
                else:
                    regular_count += 1
                    # For regular tiles, use apartment color
                    if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                        x, y = poly.exterior.xy
                        plt.fill(x, y, color=apt_color, alpha=0.3, edgecolor='gray', linewidth=0.1)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', alpha=0.7, edgecolor='black', label='Small Tiles'),
            Patch(facecolor='lightgray', alpha=0.3, edgecolor='gray', label='Regular Tiles')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.title(f"All Tiles with Small Tiles Highlighted ({small_count} small tiles, {regular_count} regular tiles)")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        # Don't show the plot - let the caller handle it
        return small_count, regular_count

    def visualize_small_tiles(self, tiles_df, small_tiles_df, final_room_df, size_threshold=10):
        """Visualize small cut tiles in context of all tiles"""
        print(f"\n🎨 Visualizing tiles with cut dimension < {size_threshold}mm...")
        
        plt.figure(figsize=(16, 16))
        
        # Plot room outlines
        for _, room in final_room_df.iterrows():
            room_poly = room['polygon']
            x, y = room_poly.exterior.xy
            plt.plot(x, y, color='black', linewidth=1.5, alpha=0.8)
            
            # Add room label
            plt.text(room['centroid_x'], room['centroid_y'], 
                     f"{room['apartment_name']}-{room['room_name']}", 
                     fontsize=10, ha='center', va='center', 
                     bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))
        
        # Define colors for different types
        colors = {
            'full': 'lightgray',
            'irregular': 'lightblue',
            'cut_normal': 'lightgreen',
            'small_cut': 'red',
            'unknown': 'gray'
        }
        
        # First, plot all non-small tiles with lighter colors
        for _, tile in tiles_df.iterrows():
            classification = tile['classification']
            is_small_cut = False
            
            # Check if this is a cut tile
            is_cut = classification in ['cut_x', 'cut_y', 'all_cut']
            
            # For cut tiles, check if they're in the small tiles DataFrame
            if is_cut and not small_tiles_df.empty:
                is_small_cut = (tile['tile_index'] in small_tiles_df['tile_index'].values and 
                              tile['apartment_name'] == small_tiles_df.loc[small_tiles_df['tile_index'] == tile['tile_index'], 'apartment_name'].values[0])
            
            # Skip small cut tiles for now (will plot them later)
            if is_small_cut:
                continue
                
            # Choose color based on classification
            if classification == 'full':
                color = colors['full']
            elif classification == 'irregular':
                color = colors['irregular']
            elif is_cut:
                color = colors['cut_normal']
            else:
                color = colors['unknown']
                
            poly = tile['polygon']
            
            try:
                if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                    x, y = poly.exterior.xy
                    plt.fill(x, y, color=color, alpha=0.5, edgecolor='black', linewidth=0.5)
                elif isinstance(poly, MultiPolygon):
                    for part in poly.geoms:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color=color, alpha=0.5, edgecolor='black', linewidth=0.5)
            except Exception as e:
                print(f"Error plotting tile: {e}")
        
        # Now plot the small cut tiles on top with bright red color
        for _, tile in small_tiles_df.iterrows():
            poly = tile['polygon']
            
            try:
                if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                    x, y = poly.exterior.xy
                    plt.fill(x, y, color=colors['small_cut'], alpha=0.9, edgecolor='black', linewidth=1.0)
                    
                    # Add cut dimension label
                    centroid = poly.centroid
                    cut_size = tile['cut_side']
                    plt.text(centroid.x, centroid.y, f"{cut_size:.1f}", 
                             fontsize=8, ha='center', va='center', color='white',
                             bbox=dict(facecolor='red', alpha=0.7, boxstyle='round,pad=0.1'))
                    
                elif isinstance(poly, MultiPolygon):
                    for part in poly.geoms:
                        if part.is_valid and not part.is_empty:
                            x, y = part.exterior.xy
                            plt.fill(x, y, color=colors['small_cut'], alpha=0.9, edgecolor='black', linewidth=1.0)
            except Exception as e:
                print(f"Error plotting small tile: {e}")
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=colors['full'], alpha=0.5, edgecolor='black', label='Full Tiles'),
            Patch(facecolor=colors['irregular'], alpha=0.5, edgecolor='black', label='Irregular Tiles'),
            Patch(facecolor=colors['cut_normal'], alpha=0.5, edgecolor='black', label='Normal Cut Tiles'),
            Patch(facecolor=colors['small_cut'], alpha=0.9, edgecolor='black', label=f'Small Cut Tiles (< {size_threshold}mm)')
        ]
        
        plt.legend(handles=legend_elements, loc='upper right')
        
        plt.title(f"Small Cut Tiles (< {size_threshold}mm) Visualization")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        
        # Don't show - let the caller handle it
        return True

    def visualize_apartment_tiles(self, apartment_name, tiles_subset, rooms_subset, group_mapping, tile_specs_to_groups, tile_width, tile_height, get_tile_color_func):
        """Create visualization for a specific apartment with matching colors"""
        fig, ax = plt.subplots(figsize=(16, 16))
        
        # Ensure we have valid data
        if tiles_subset.empty or rooms_subset.empty:
            ax.text(0.5, 0.5, f"No data available for {apartment_name}", 
                    ha='center', va='center', transform=ax.transAxes, fontsize=20)
            plt.tight_layout()
            return {'Full Tile': 0, 'Irregular Tile': 0, 'Matched (Apartment)': 0, 
                    'Matched (Inventory)': 0, 'Unmatched': 0}
        
        # Plot room boundaries
        room_plotted = False
        for _, room in rooms_subset.iterrows():
            room_poly = room.get('polygon')
            if room_poly is None:
                continue
                
            if isinstance(room_poly, Polygon):
                try:
                    x, y = room_poly.exterior.xy
                    ax.plot(x, y, color='black', linewidth=2, alpha=0.8)
                    room_plotted = True
                    
                    # Add room label
                    if 'centroid_x' in room and 'centroid_y' in room:
                        ax.text(room['centroid_x'], room['centroid_y'], 
                            f"{room.get('room_name', '')}", 
                            fontsize=12, ha='center', va='center', 
                            bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3'))
                except Exception as e:
                    print(f"Error plotting room boundary: {e}")
        
        if not room_plotted:
            print(f"Warning: No room boundaries plotted for {apartment_name}")
        
        # Counters for legend
        color_counts = {}
        match_type_counts = {'Full Tile': 0, 'Irregular Tile': 0, 'Matched (Apartment)': 0, 
                        'Matched (Inventory)': 0, 'Unmatched': 0}
        
        # Track if any tiles were plotted
        tiles_plotted = 0
        
        # Plot tiles with colors
        for idx, tile_row in tiles_subset.iterrows():
            poly = tile_row.get('polygon')
            
            if poly is None:
                print(f"Warning: No polygon for tile at index {idx}")
                continue
                
            if isinstance(poly, (Polygon, MultiPolygon)):
                try:
                    # Get color for this tile using group-based matching
                    color, match_type, group_id = get_tile_color_func(tile_row, group_mapping, tile_specs_to_groups, tile_width, tile_height)
                    
                    # Count colors and match types
                    if color not in color_counts:
                        color_counts[color] = 0
                    color_counts[color] += 1
                    
                    if 'Full' in match_type:
                        match_type_counts['Full Tile'] += 1
                    elif 'Irregular' in match_type:
                        match_type_counts['Irregular Tile'] += 1
                    elif 'Apartment' in match_type:
                        match_type_counts['Matched (Apartment)'] += 1
                    elif 'Inventory' in match_type:
                        match_type_counts['Matched (Inventory)'] += 1
                    else:
                        match_type_counts['Unmatched'] += 1
                    
                    # Plot the tile
                    if isinstance(poly, Polygon):
                        if poly.is_valid and not poly.is_empty:
                            # Convert to matplotlib polygon
                            coords = list(poly.exterior.coords)
                            mpl_poly = MplPolygon(coords, facecolor=color, edgecolor='black', 
                                                linewidth=0.3, alpha=0.8)
                            ax.add_patch(mpl_poly)
                            tiles_plotted += 1
                            
                            # Add group ID label for matched tiles
                            if group_id and group_id != '':
                                centroid = poly.centroid
                                ax.text(centroid.x, centroid.y, group_id, 
                                    fontsize=6, ha='center', va='center', 
                                    color='black', weight='bold')
                    
                    elif isinstance(poly, MultiPolygon):
                        for part in poly.geoms:
                            if part.is_valid and not part.is_empty:
                                coords = list(part.exterior.coords)
                                mpl_poly = MplPolygon(coords, facecolor=color, edgecolor='black', 
                                                    linewidth=0.3, alpha=0.8)
                                ax.add_patch(mpl_poly)
                                tiles_plotted += 1
                except Exception as e:
                    print(f"Error plotting tile: {e}")
        
        print(f"Plotted {tiles_plotted} tiles for {apartment_name}")
        
        # Create legend
        legend_elements = []
        
        # Color definitions for legend
        FULL_TILE_COLOR = '#E6E6FA'
        IRREGULAR_COLOR = '#F0E68C'
        SAME_APT_COLORS = ['#FFD700']
        INV_COLOR = '#8FBC8F'
        UNMATCHED_COLOR = '#FFFFFF'
        
        # Add match type legend
        if match_type_counts['Full Tile'] > 0:
            legend_elements.append(patches.Patch(color=FULL_TILE_COLOR, 
                                            label=f"Full Tiles ({match_type_counts['Full Tile']})"))
        
        if match_type_counts['Irregular Tile'] > 0:
            legend_elements.append(patches.Patch(color=IRREGULAR_COLOR, 
                                            label=f"Irregular Tiles ({match_type_counts['Irregular Tile']})"))
        
        if match_type_counts['Matched (Apartment)'] > 0:
            legend_elements.append(patches.Patch(color=SAME_APT_COLORS[0],
                                            label=f"Apartment Matches ({match_type_counts['Matched (Apartment)']})"))
        
        if match_type_counts['Matched (Inventory)'] > 0:
            legend_elements.append(patches.Patch(color=INV_COLOR, 
                                            label=f"Inventory Matches ({match_type_counts['Matched (Inventory)']})"))
        
        if match_type_counts['Unmatched'] > 0:
            legend_elements.append(patches.Patch(color=UNMATCHED_COLOR, 
                                            label=f"Unmatched Cuts ({match_type_counts['Unmatched']})"))
        
        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))
        
        # Set title and formatting
        total_tiles = len(tiles_subset)
        matched_tiles = match_type_counts['Matched (Apartment)'] + match_type_counts['Matched (Inventory)']
        
        ax.set_title(f"{apartment_name} - Tile Layout with Matching Colors\n"
                    f"Total: {total_tiles} tiles | Matched: {matched_tiles} | "
                    f"Full: {match_type_counts['Full Tile']} | "
                    f"Unmatched: {match_type_counts['Unmatched']}", 
                    fontsize=14, pad=20)
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('X Coordinate (mm)')
        ax.set_ylabel('Y Coordinate (mm)')
        
        # Add color coding explanation
        explanation_text = (
            "Color Coding:\n"
            "• Same colors = Matched pieces\n"
            "• Gray = Different apartment matches\n"
            "• Green = Inventory matches\n"
            "• White = Unmatched pieces"
        )
        
        ax.text(0.02, 0.02, explanation_text, transform=ax.transAxes, 
            fontsize=10, verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        # Auto-adjust the view to show all data
        ax.autoscale()
        
        # Don't call plt.show() here - let the caller handle it
        
        # Print summary
        print(f"\n📊 {apartment_name} Summary:")
        print(f"   Total tiles: {total_tiles}")
        print(f"   Full tiles: {match_type_counts['Full Tile']}")
        print(f"   Irregular tiles: {match_type_counts['Irregular Tile']}")
        print(f"   Apartment matches: {match_type_counts['Matched (Apartment)']}")
        print(f"   Inventory matches: {match_type_counts['Matched (Inventory)']}")
        print(f"   Unmatched cuts: {match_type_counts['Unmatched']}")
        
        return match_type_counts
    
    def plot_clusters_with_positions(self, clusters_df, use_final_names=False):
        """FINAL VERSION - Correct positioning using start points and proper scale"""
        import matplotlib.pyplot as plt
        import io
        import base64
        
        print("\n=== STARTING PLOT GENERATION ===")
        
        # Create plot with EXACT dimensions
        fig, ax = plt.subplots(figsize=(18, 12))  # Fixed size for consistent scaling
        unique_clusters = clusters_df['apartment_cluster'].unique()

        if use_final_names and 'apartment_name' in clusters_df.columns:
            apartment_names = clusters_df.groupby('apartment_cluster')['apartment_name'].first().to_dict()
            self.apartment_names.update(apartment_names)
        else:
            apartment_names = {cluster_id: f"Apartment {cluster_id+1}" for cluster_id in unique_clusters}

        # Step 1: Get start points from session
        start_points_data = []
        try:
            from flask import session
            start_points_data = session.get('start_points_data', [])
            print(f"Loaded {len(start_points_data)} start points from session")
        except Exception as e:
            print(f"Error loading start points: {e}")
        
        # Step 2: Create start point mapping
        start_point_map = {}
        for sp in start_points_data:
            room_id = sp.get('room_id', -1)
            if room_id >= 0 and 'centroid' in sp:
                start_point_map[room_id] = {
                    'x': float(sp['centroid'][0]),
                    'y': float(sp['centroid'][1])
                }
        print(f"Mapped {len(start_point_map)} start points to rooms")

        # Step 3: Plot rooms and collect coordinates
        all_x_coords = []
        all_y_coords = []
        room_data = []
        apartment_data = {}
        
        for cluster_id in unique_clusters:
            cluster_rooms = clusters_df[clusters_df['apartment_cluster'] == cluster_id]
            color = self.get_color(cluster_id)
            apt_name = self.apartment_names.get(cluster_id, apartment_names.get(cluster_id, f"Apartment {cluster_id+1}"))
            
            # Initialize apartment data
            apartment_data[cluster_id] = {
                'name': apt_name,
                'room_positions': [],
                'bounds': {'min_x': float('inf'), 'max_x': float('-inf'), 
                          'min_y': float('inf'), 'max_y': float('-inf')}
            }
            
            for idx, row in cluster_rooms.iterrows():
                polygon = row['polygon']
                x_coords, y_coords = polygon.exterior.xy
                
                # Plot the room (with label for first room of each apartment)
                ax.fill(x_coords, y_coords, alpha=0.6, 
                       label=apt_name if idx == cluster_rooms.index[0] else "", 
                       color=color)
                
                # Collect all coordinates for overall bounds
                all_x_coords.extend(x_coords)
                all_y_coords.extend(y_coords)
                
                # Update apartment bounds
                bounds = apartment_data[cluster_id]['bounds']
                bounds['min_x'] = min(bounds['min_x'], min(x_coords))
                bounds['max_x'] = max(bounds['max_x'], max(x_coords))
                bounds['min_y'] = min(bounds['min_y'], min(y_coords))
                bounds['max_y'] = max(bounds['max_y'], max(y_coords))
                
                # Determine room center position
                room_id = int(row['room_id'])
                
                if room_id in start_point_map:
                    # Use start point (PREFERRED - most accurate for tiles)
                    room_x = start_point_map[room_id]['x']
                    room_y = start_point_map[room_id]['y']
                    position_source = "START_POINT"
                else:
                    # Fallback to room centroid
                    room_x = float(row['centroid_x'])
                    room_y = float(row['centroid_y'])
                    position_source = "CENTROID"
                
                print(f"Room {room_id} ({row['room_name']}): {position_source} at ({room_x:.0f}, {room_y:.0f})")
                
                # Store room data
                room_info = {
                    'room_id': room_id,
                    'room_name': str(row['room_name']),
                    'apartment_name': str(row.get('apartment_name', apt_name)),
                    'x': room_x,
                    'y': room_y,
                    'apartment_cluster': int(cluster_id),
                    'type': 'room'
                }
                
                room_data.append(room_info)
                apartment_data[cluster_id]['room_positions'].append((room_x, room_y))

        # Step 4: Configure plot without legend (to prevent squeezing)
        ax.set_title("🏢 Apartment Clusters with Room Names", fontsize=16, pad=20)
        ax.grid(True, alpha=0.3)
        
        # Step 5: Set EXACT plot bounds
        data_min_x, data_max_x = min(all_x_coords), max(all_x_coords)
        data_min_y, data_max_y = min(all_y_coords), max(all_y_coords)
        
        data_width = data_max_x - data_min_x
        data_height = data_max_y - data_min_y
        
        # Add consistent padding
        padding_percent = 0.05  # 5% padding on all sides
        padding_x = data_width * padding_percent
        padding_y = data_height * padding_percent
        
        # Final plot bounds
        plot_min_x = data_min_x - padding_x
        plot_max_x = data_max_x + padding_x
        plot_min_y = data_min_y - padding_y
        plot_max_y = data_max_y + padding_y
        
        ax.set_xlim(plot_min_x, plot_max_x)
        ax.set_ylim(plot_min_y, plot_max_y)
        ax.set_aspect('equal')  # Maintain aspect ratio
        
        # Calculate final plot dimensions
        plot_width = plot_max_x - plot_min_x
        plot_height = plot_max_y - plot_min_y
        
        print(f"\nPlot bounds: X({plot_min_x:.0f} to {plot_max_x:.0f}), Y({plot_min_y:.0f} to {plot_max_y:.0f})")
        print(f"Plot size: {plot_width:.0f} x {plot_height:.0f}")
        
        # Step 6: Calculate apartment label positions - FIXED to use true centroids + slight upward offset
        apartment_data_final = []
        
        for cluster_id, apt_info in apartment_data.items():
            if not apt_info['room_positions']:
                continue
            
            room_positions = apt_info['room_positions']
            bounds = apt_info['bounds']
            
            # Calculate TRUE apartment geometric center (average of room positions)
            center_x = sum(x for x, y in room_positions) / len(room_positions)
            center_y = sum(y for x, y in room_positions) / len(room_positions)
            
            # Calculate apartment dimensions for offset calculation
            apt_width = bounds['max_x'] - bounds['min_x']
            apt_height = bounds['max_y'] - bounds['min_y']
            
            # Move apartment label SLIGHTLY ABOVE center (adjust this value as needed)
            upward_offset_percent = 0.50  # 12% of apartment height above center
            apt_label_x = center_x
            apt_label_y = center_y + (apt_height * upward_offset_percent)
            
            # Check if this position conflicts with any room in this apartment
            min_distance_to_rooms = min(
                ((apt_label_x - rx)**2 + (apt_label_y - ry)**2)**0.5
                for rx, ry in room_positions
            )
            
            # Only try alternatives if there's a significant conflict
            min_safe_distance = min(apt_width, apt_height) * 0.08
            
            if min_distance_to_rooms < min_safe_distance:
                print(f"Apartment {apt_info['name']}: above-center conflicts, trying alternatives...")
                
                # Try alternative positions around the center
                alternatives = [
                    # Original above position (keep trying this first)
                    (center_x, center_y + apt_height * upward_offset_percent),
                    # Further above
                    (center_x, center_y + apt_height * 0.20),
                    # Slightly less above
                    (center_x, center_y + apt_height * 0.08),
                    # Above-left
                    (center_x - apt_width * 0.15, center_y + apt_height * 0.10),
                    # Above-right
                    (center_x + apt_width * 0.15, center_y + apt_height * 0.10),
                    # Pure center as last resort
                    (center_x, center_y)
                ]
                
                best_position = alternatives[0]  # Default to above-center
                best_distance = min_distance_to_rooms
                
                for alt_x, alt_y in alternatives:
                    min_dist = min(
                        ((alt_x - rx)**2 + (alt_y - ry)**2)**0.5
                        for rx, ry in room_positions
                    )
                    
                    if min_dist > best_distance:
                        best_distance = min_dist
                        best_position = (alt_x, alt_y)
                
                apt_label_x, apt_label_y = best_position
                print(f"  -> Moved to ({apt_label_x:.0f}, {apt_label_y:.0f}) with distance {best_distance:.0f}")
            else:
                print(f"Apartment {apt_info['name']}: using above-center ({apt_label_x:.0f}, {apt_label_y:.0f}) - no conflicts")
            
            apartment_data_final.append({
                'apartment_cluster': int(cluster_id),
                'apartment_name': apt_info['name'],
                'x': apt_label_x,
                'y': apt_label_y,
                'type': 'apartment'
            })

        # Step 7: Convert to percentage coordinates for web overlay
        print(f"\n=== COORDINATE CONVERSION ===")
        
        final_positions = []
        
        # Convert room positions
        for room in room_data:
            # Normalize to 0-1
            norm_x = (room['x'] - plot_min_x) / plot_width
            norm_y = (room['y'] - plot_min_y) / plot_height
            
            # Convert to percentage with Y-flip for web
            web_x = norm_x * 100
            web_y = (1.0 - norm_y) * 100
            
            final_positions.append({
                'room_id': room['room_id'],
                'room_name': room['room_name'],
                'apartment_name': room['apartment_name'],
                'centroid_x': room['x'],
                'centroid_y': room['y'],
                'apartment_cluster': room['apartment_cluster'],
                'x_percent': web_x,
                'y_percent': web_y,
                'type': 'room'
            })
            
            print(f"Room {room['room_name']}: ({room['x']:.0f}, {room['y']:.0f}) -> ({web_x:.1f}%, {web_y:.1f}%)")
        
        # Convert apartment positions
        for apt in apartment_data_final:
            # Normalize to 0-1
            norm_x = (apt['x'] - plot_min_x) / plot_width
            norm_y = (apt['y'] - plot_min_y) / plot_height
            
            # Convert to percentage with Y-flip for web
            web_x = norm_x * 100
            web_y = (1.0 - norm_y) * 100
            
            final_positions.append({
                'apartment_cluster': apt['apartment_cluster'],
                'apartment_name': apt['apartment_name'],
                'centroid_x': apt['x'],
                'centroid_y': apt['y'],
                'x_percent': web_x,
                'y_percent': web_y,
                'type': 'apartment'
            })
            
            print(f"Apt {apt['apartment_name']}: ({apt['x']:.0f}, {apt['y']:.0f}) -> ({web_x:.1f}%, {web_y:.1f}%)")

        # Step 8: Generate final plot
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, 
                   facecolor='white', pad_inches=0.05)
        plt.close()
        buf.seek(0)
        plot_b64 = base64.b64encode(buf.read()).decode('utf-8')
        
        print(f"\n=== GENERATION COMPLETE ===")
        print(f"Created plot with {len([p for p in final_positions if p['type'] == 'room'])} rooms and {len([p for p in final_positions if p['type'] == 'apartment'])} apartments")
        
        return plot_b64, final_positions