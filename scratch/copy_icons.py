import os
import shutil

def copy_icons():
    src_dir = r"c:\Users\bradr\OneDrive\Documents\GitHub\events-system\public\icons"
    dest_dir = r"c:\Users\bradr\OneDrive\Documents\GitHub\events-system\frontend\static\icons"
    
    os.makedirs(dest_dir, exist_ok=True)
    
    # List files in src
    files = [f for f in os.listdir(src_dir) if f.endswith('.svg')]
    print(f"Copying {len(files)} icons from {src_dir} to {dest_dir}...")
    
    for f in files:
        src_path = os.path.join(src_dir, f)
        dest_path = os.path.join(dest_dir, f)
        shutil.copy2(src_path, dest_path)
        print(f"  Copied {f}")
        
if __name__ == '__main__':
    copy_icons()
