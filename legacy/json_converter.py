import json
import os
import csv
from PIL import Image

# Your label maps here
FORM_MAP = {
    'Typo': 0,
    'Image': 1,
    'Icon': 2,
    'Space': 3
}

FUNCTION_MAP = {
    'Dropdown': 0, 'Radio button': 1, 'Checkbox': 2, 'Text input': 3, 'Label': 4,
    'Text': 5, 'Breadcrumb': 6, 'Button': 7, 'Link': 8, 'Ad': 9,
    'Tag': 10, 'Heading': 11, 'Illustration': 12
}

COMPONENT_MAP = {
    'Carousel': 0, 'Card': 1, 'Table': 2, 'Search bar': 3, 'Banner': 4,
    'Menu': 5, 'Filter': 6, 'Tab': 7, 'List item': 8, 'Blank': 9
}

TAXONOMY_MAP = {
    'Header': 0, 'Sub-header': 1, 'Footer': 2, 'Column 0': 3, 'Column 1': 4,
    'Column 2': 5, 'Column 3': 6, 'Column 4': 7, 'Left Panel': 8,
    'Right Panel': 9, 'Left Menu': 10, 'Right Menu': 11
}


# Paths
json_folder = 'C:/Users/bruno/Documents/Annotation tool/json'
image_folder = 'C:/Users/bruno/Documents/Annotation tool/images'
yolo_labels_folder = 'C:/Users/bruno/Documents/Annotation tool/labels'
classifier_csv_path = 'C:/Users/bruno/Documents/Annotation tool/csv/test.csv'

# Create YOLO labels folder if not exists
os.makedirs(yolo_labels_folder, exist_ok=True)

# Open CSV file for classifier labels
with open(classifier_csv_path, mode='w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['image_id', 'bbox_id', 'x_min', 'y_min', 'x_max', 'y_max',
                     'Form_label', 'Function_label', 'Component_label', 'Taxonomy_label'])
    
    # Loop over JSON files
    for json_file in os.listdir(json_folder):
        if not json_file.endswith('.json'):
            continue
        
        json_path = os.path.join(json_folder, json_file)
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Assume image name matches JSON name (you can adapt this)
        image_name = os.path.splitext(json_file)[0] + '.png'
        image_path = os.path.join(image_folder, image_name)
        
        # Load image to get size
        img = Image.open(image_path)
        img_w, img_h = img.size
        
        # Prepare YOLO label file
        yolo_label_path = os.path.join(yolo_labels_folder,
                                       os.path.splitext(json_file)[0] + '.txt')
        with open(yolo_label_path, 'w') as yolo_f:
            for idx, selection in enumerate(data['selections']):
                # Read coords
                x_min, y_min, x_max, y_max = selection['coords']
                
                # Convert to YOLO format
                x_center = (x_min + x_max) / 2 / img_w
                y_center = (y_min + y_max) / 2 / img_h
                width = (x_max - x_min) / img_w
                height = (y_max - y_min) / img_h
                
                # YOLO format: "0 x_center y_center width height" (class 0 → element)
                yolo_f.write(f'0 {x_center} {y_center} {width} {height}\n')
                
                # Prepare classifier labels
                form_label = FORM_MAP[selection['Form']]
                function_label = FUNCTION_MAP[selection['Function']]
                component_label = COMPONENT_MAP[selection['Component']]
                taxonomy_label = TAXONOMY_MAP[selection['Taxonomy']]
                
                # Write to CSV
                writer.writerow([image_name, f'box_{idx}', x_min, y_min, x_max, y_max,
                                 form_label, function_label, component_label, taxonomy_label])

print("✅ Conversion done!")