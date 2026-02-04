"""Debug script to check image paths"""

import json
from pathlib import Path

# Load questions.json directly
questions_file = Path("data/questions.json")

if not questions_file.exists():
    print("❌ questions.json not found!")
    exit()

with open(questions_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total questions: {data['total_count']}")
print(f"With images (metadata): {data.get('with_images', 'N/A')}")

# Check image paths
questions_with_images = []
questions_needing_images = []

for q in data['questions']:
    images = q.get('images', [])
    has_ref = q.get('has_image_reference', False)
    
    if images:
        questions_with_images.append({
            'id': q['id'],
            'text': q['question_text'][:60],
            'images': images,
            'images_exist': [Path(p).exists() if not p.startswith('data:') else True for p in images]
        })
    elif has_ref:
        questions_needing_images.append({
            'id': q['id'],
            'text': q['question_text'][:60],
            'pattern': q.get('image_pattern_matched', 'N/A')
        })

print(f"\n📷 Questions WITH image paths: {len(questions_with_images)}")
print(f"⚠️ Questions NEEDING images: {len(questions_needing_images)}")

# Show details
print("\n" + "="*60)
print("QUESTIONS WITH IMAGE PATHS:")
print("="*60)

for i, q in enumerate(questions_with_images[:10]):
    print(f"\n--- {i+1}. {q['text']}...")
    for j, img in enumerate(q['images']):
        exists = q['images_exist'][j]
        status = "✅" if exists else "❌"
        print(f"    {status} Image: {img[:80]}...")
        
        # Check if relative path needs DATA_DIR
        if not exists and not img.startswith('data:'):
            # Try with data/ prefix
            alt_path = Path("data") / img
            if alt_path.exists():
                print(f"    ⚠️ BUT EXISTS at: {alt_path}")

# Check images folder
print("\n" + "="*60)
print("IMAGES FOLDER CHECK:")
print("="*60)

images_dir = Path("data/processed/images")
if images_dir.exists():
    image_files = list(images_dir.glob("*"))
    print(f"Found {len(image_files)} files in {images_dir}")
    for f in image_files[:10]:
        print(f"  • {f.name} ({f.stat().st_size} bytes)")
else:
    print(f"❌ Images directory not found: {images_dir}")