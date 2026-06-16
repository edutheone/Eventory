import os
import xml.etree.ElementTree as ET
from collections import Counter

def check_new_icons(directory):
    files = sorted([f for f in os.listdir(directory) if f.endswith('.svg')])
    print(f"Analyzing {len(files)} new SVGs in {directory}:\n")
    
    for f in files:
        path = os.path.join(directory, f)
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            
            paths = root.findall('.//path')
            if not paths:
                ns = {'svg': 'http://www.w3.org/2000/svg'}
                paths = root.findall('.//svg:path', ns)
                
            fills = []
            strokes = []
            for p in paths:
                fill = p.get('fill')
                if fill:
                    fills.append(fill)
                stroke = p.get('stroke')
                if stroke:
                    strokes.append(stroke)
            
            fill_counts = Counter(fills)
            stroke_counts = Counter(strokes)
            
            print(f"File: {f} (paths: {len(paths)})")
            if fill_counts:
                print(f"  Fills: {dict(fill_counts)}")
            if stroke_counts:
                print(f"  Strokes: {dict(stroke_counts)}")
        except Exception as e:
            print(f"Error parsing {f}: {e}")

if __name__ == '__main__':
    check_new_icons(r"c:\Users\bradr\OneDrive\Documents\GitHub\events-system\public\icons")
