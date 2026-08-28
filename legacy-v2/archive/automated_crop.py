import os
import pandas as pd
from osgeo import gdal

gdal.UseExceptions()

INPUT_DIR = "."
OUTPUT_DIR = "CROPPED_IMAGES"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bangka_dataset.csv'))
existing_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.jpg', '.tif', '.png'))]

print("Cropping map legends based on pixel data...\n" + "-"*50)

success = 0
skipped = []

for index, row in df.iterrows():
    sheet_id = row['sheet_id']
    image_idx = row['image_idx']

    found_file = None
    search_prefix = f"{int(image_idx):03d}_"
    for file in existing_files:
        if file.startswith(search_prefix):
            found_file = file
            break

    if not found_file:
        continue

    input_path = os.path.join(INPUT_DIR, found_file)
    output_path = os.path.join(OUTPUT_DIR, found_file)

    try:
        # Flexible check in case column names got truncated
        ml = int(row['margin_left']) if 'margin_left' in df.columns else int(row['margin_lef'])
        mt = int(row['margin_top'])
        cw = int(row['crop_w'])
        ch = int(row['crop_h'])

        # Crop setting based on the pixel window
        options = gdal.TranslateOptions(srcWin=[ml, mt, cw, ch])
        out_ds = gdal.Translate(output_path, input_path, options=options)
        out_ds = None

        success += 1
        print(f"Cropped: {found_file}")

    except Exception as e:
        skipped.append((sheet_id, str(e)))

print("-" * 50)
print(f"Stage 1 done! {success} maps cleaned of legends and saved to '{OUTPUT_DIR}'.")
