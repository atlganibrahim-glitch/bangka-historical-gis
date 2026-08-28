import pandas as pd
from PIL import Image
import cv2
import numpy as np
import os

# --- SETTINGS ---
# v2-era script; run from the true repo root (main maps/ and recovered_maps/
# stayed there). archive/ moved into legacy-v2/ alongside this script.
csv_path = os.path.join('legacy-v2', 'archive', 'bangka_dataset.csv')
input_dir = 'main maps'  # Raw scans live in this folder
output_dir = 'recovered_maps'
os.makedirs(output_dir, exist_ok=True)

# Read the dataset
df = pd.read_csv(csv_path)

print("Starting cropping with the exact ratio from Paint...")
print("Bottom margin set to 15.89%. Keeps the island, drops the legend!\n")

success = 0

for index, row in df.iterrows():
    img_name = row['filename']
    crop_name = row['crop_filename']

    img_path = os.path.join(input_dir, img_name)
    if not os.path.exists(img_path):
        # Check upper/lower case variations
        if os.path.exists(os.path.join(input_dir, img_name.lower())):
            img_path = os.path.join(input_dir, img_name.lower())
        elif os.path.exists(os.path.join(input_dir, img_name.upper())):
            img_path = os.path.join(input_dir, img_name.upper())
        else:
            continue

    # 1. SAFE READ (for non-ASCII characters in the path)
    try:
        stream = open(img_path, "rb")
        bytes_data = bytearray(stream.read())
        numpyarray = np.asarray(bytes_data, dtype=np.uint8)
        cv2_img = cv2.imdecode(numpyarray, cv2.IMREAD_UNCHANGED)
        stream.close()
    except Exception as e:
        print(f"Read error: {img_name} - {e}")
        continue

    if cv2_img is None:
        print(f"Could not read (file may be corrupt): {img_name}")
        continue

    # Convert OpenCV to PIL (for the crop operation)
    cv2_img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(cv2_img_rgb)

    # 2. HYBRID RATIOS AND CROP
    w = row['width_px']
    h = row['height_px']
    m_left = row['margin_left']
    m_right = row['margin_right']
    m_top = row['margin_top']

    # THE UPDATED, EXACT RATIO:
    # Moved 250 px higher than the old 4352; new Y coordinate: 4102
    m_bottom = 1 - (4102 / 5174)

    left = int(w * m_left)
    top = int(h * m_top)
    right = int(w * (1 - m_right))
    bottom = int(h * (1 - m_bottom))

    try:
        # Crop with PIL
        cropped_img = img.crop((left, top, right, bottom))

        # 3. SAFE SAVE (for non-ASCII characters in the path)
        cv2_cropped = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2BGR)

        output_path = os.path.join(output_dir, crop_name)
        ext = os.path.splitext(crop_name)[1]
        if not ext:
            ext = '.jpg'

        is_success, im_buf_arr = cv2.imencode(ext, cv2_cropped)
        if is_success:
            im_buf_arr.tofile(output_path)
            print(f"Success: {img_name} -> {crop_name}")
            success += 1
        else:
            print(f"Could not save: {img_name}")

    except Exception as e:
        print(f"Crop/Save error ({img_name}): {e}")

print(f"\nDone! {success} maps cropped successfully.")
