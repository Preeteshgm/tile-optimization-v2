# utility_functions.py
import pandas as pd
import numpy as np
from shapely.geometry import Polygon

def get_bounding_box(polygon):
    """Get the bounding box of a polygon"""
    minx, miny, maxx, maxy = polygon.bounds
    return Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])

def get_tile_centroid(tile_polygon):
    """Get the centroid of a tile polygon"""
    return tile_polygon.centroid

def display_dataframe(df, title):
    """Displays a DataFrame in a way that works in web apps."""
    print(f"\n{title}:")
    print(f"Total rows: {len(df)}")
    
    # For web app, just print the dataframe
    if len(df) > 20:
        print(df.head(20).to_string())
        print(f"... showing first 20 of {len(df)} rows")
    else:
        print(df.to_string())

def format_number(num):
    """Format number with commas"""
    return "{:,}".format(int(num))

def format_percentage(value, decimal_places=1):
    """Format percentage with specified decimal places"""
    return f"{value:.{decimal_places}f}%"

def safe_divide(numerator, denominator, default=0):
    """Safely divide two numbers, returning default if denominator is zero"""
    if denominator == 0:
        return default
    return numerator / denominator

def serialize_polygon(polygon):
    """Convert a Shapely polygon to a serializable format"""
    if polygon is None:
        return None
    return {
        'coords': list(polygon.exterior.coords),
        'bounds': polygon.bounds,
        'area': polygon.area
    }

def deserialize_polygon(polygon_data):
    """Convert serialized polygon data back to Shapely polygon"""
    if polygon_data is None:
        return None
    return Polygon(polygon_data['coords'])

def get_polygon_dimensions(polygon):
    """Get width and height of a polygon's bounding box"""
    if polygon is None:
        return 0, 0
    minx, miny, maxx, maxy = polygon.bounds
    width = maxx - minx
    height = maxy - miny
    return width, height

def is_rectangular(polygon, tolerance=0.95):
    """Check if a polygon is approximately rectangular"""
    if polygon is None:
        return False
    
    # Get bounding box
    bbox = get_bounding_box(polygon)
    
    # Compare areas
    polygon_area = polygon.area
    bbox_area = bbox.area
    
    if bbox_area == 0:
        return False
    
    # If polygon area is at least tolerance% of bbox area, consider it rectangular
    return (polygon_area / bbox_area) >= tolerance

def calculate_wastage_percentage(actual_area, required_area):
    """Calculate wastage percentage"""
    if required_area == 0:
        return 0
    wastage = actual_area - required_area
    return (wastage / required_area) * 100

def round_to_nearest(value, nearest=1):
    """Round value to nearest specified increment"""
    return round(value / nearest) * nearest

# Export all functions
__all__ = [
    'get_bounding_box',
    'get_tile_centroid',
    'display_dataframe',
    'format_number',
    'format_percentage',
    'safe_divide',
    'serialize_polygon',
    'deserialize_polygon',
    'get_polygon_dimensions',
    'is_rectangular',
    'calculate_wastage_percentage',
    'round_to_nearest'
]