"""FMGE Practice Engine - Command Line Interface"""

import argparse
import sys
from pathlib import Path
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def cmd_detect(args):
    """Detect PDF formats"""
    from core.format_detector import FormatDetector
    
    detector = FormatDetector()
    directory = Path(args.input_dir) if args.input_dir else Path("data/raw_pdfs")
    
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        return
    
    detector.print_detection_report(directory)


def cmd_process(args):
    """Process PDFs and build question bank"""
    from core.pdf_parser import UniversalPDFParser
    from core.question_cleaner import QuestionCleaner
    from storage.json_storage import QuestionStorage
    
    print("="*60)
    print("FMGE Practice Engine - Universal PDF Processor")
    print("="*60)
    
    parser = UniversalPDFParser(
        extract_images=not args.no_images,
        save_images=True
    )
    cleaner = QuestionCleaner()
    storage = QuestionStorage()
    
    input_dir = Path(args.input_dir) if args.input_dir else Path("data/raw_pdfs")
    
    if not input_dir.exists():
        print(f"❌ Directory not found: {input_dir}")
        return
    
    print(f"\n📂 Processing PDFs from: {input_dir}")
    raw_questions = parser.parse_directory(input_dir)
    
    parser.print_stats()
    
    if not raw_questions:
        print("\n⚠️  No questions extracted!")
        return
    
    print(f"\n🧹 Cleaning {len(raw_questions)} questions...")
    clean_questions = cleaner.clean_questions(raw_questions)
    
    print(f"\n📊 Cleaning Statistics:")
    for key, value in cleaner.get_stats().items():
        print(f"   {key}: {value}")
    
    if args.append:
        added = storage.add_questions(clean_questions)
        print(f"\n✅ Added {added} new questions")
    else:
        storage.save_questions(clean_questions)
        print(f"\n✅ Saved {len(clean_questions)} questions")
    
    print("\n📚 Subject Distribution:")
    distribution = cleaner.get_subject_distribution(clean_questions)
    for subject, count in list(distribution.items())[:15]:
        print(f"   {subject}: {count}")


def cmd_stats(args):
    """Show question bank statistics"""
    from storage.json_storage import QuestionStorage
    
    storage = QuestionStorage()
    stats = storage.get_stats()
    
    print("\n📊 QUESTION BANK STATISTICS")
    print("="*50)
    
    for key, value in stats.items():
        if key == 'by_subject':
            print(f"\n📚 By Subject:")
            for subject, count in list(value.items())[:20]:
                print(f"   {subject}: {count}")
        else:
            print(f"   {key}: {value}")


def cmd_view(args):
    """View questions with image status"""
    from storage.json_storage import QuestionStorage
    
    storage = QuestionStorage()
    questions = storage.load_questions()
    
    # Categorize questions
    with_images = [q for q in questions if q.images]
    needs_images = [q for q in questions if q.has_image_reference and not q.images]
    no_image_ref = [q for q in questions if not q.has_image_reference]
    
    print(f"\n📋 QUESTION ANALYSIS")
    print("="*50)
    print(f"Total questions: {len(questions)}")
    print(f"✅ With linked images: {len(with_images)}")
    print(f"⚠️  Need image linking: {len(needs_images)}")
    print(f"📝 No image reference: {len(no_image_ref)}")
    
    if args.show_linked:
        print(f"\n✅ Questions WITH linked images:")
        for i, q in enumerate(with_images[:5]):
            print(f"\n--- Question {i+1} ---")
            print(f"Q: {q.question_text[:100]}...")
            print(f"Page: {q.page_number}")
            print(f"Pattern: {q.image_pattern_matched}")
            print(f"Image: {q.images[0][:60]}...")
    
    if args.show_missing:
        print(f"\n⚠️  Questions MISSING images:")
        for i, q in enumerate(needs_images[:10]):
            print(f"\n--- Question {i+1} ---")
            print(f"Q: {q.question_text[:100]}...")
            print(f"Page: {q.page_number}")
            print(f"Pattern matched: {q.image_pattern_matched}")
            print(f"Source: {q.source_file}")
    
    if not args.show_linked and not args.show_missing:
        print("\nUse --show-linked or --show-missing for details")


def cmd_diagnose(args):
    """Diagnose image extraction issues"""
    from core.image_handler import ImageExtractor, SmartImageLinker
    from pathlib import Path
    import fitz
    
    pdf_path = Path(args.pdf)
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return
    
    print(f"\n🔍 DIAGNOSING: {pdf_path.name}")
    print("="*60)
    
    # Extract images
    extractor = ImageExtractor()
    images_by_page = extractor.extract_from_pdf(pdf_path)
    
    print(f"\n📷 IMAGES FOUND:")
    total_images = sum(len(imgs) for imgs in images_by_page.values())
    print(f"   Total valid images: {total_images}")
    
    for page, imgs in sorted(images_by_page.items()):
        print(f"   Page {page}: {len(imgs)} images")
        for img in imgs:
            print(f"      - {img.id}: {img.width}x{img.height} @ y={img.y_position:.0f}")
    
    print(f"\n📊 Extraction stats:")
    for key, value in extractor.get_stats().items():
        print(f"   {key}: {value}")
    
    # Look for questions on first few pages
    print(f"\n📝 QUESTIONS FOUND:")
    
    doc = fitz.open(pdf_path)
    linker = SmartImageLinker()
    
    for page_num in range(min(5, len(doc))):
        page = doc[page_num]
        text = page.get_text("text")
        
        # Find question markers
        q_pattern = r'(\d{1,3})\s*\.\s*Question\s*:'
        matches = re.findall(q_pattern, text, re.IGNORECASE)
        
        if matches:
            print(f"\n   Page {page_num + 1}: Questions {', '.join(matches)}")
            
            # Check if any reference images
            for match in matches:
                # Find the question text
                q_start = text.find(f"{match}. Question")
                if q_start >= 0:
                    q_text = text[q_start:q_start+300]
                    needs_img, pattern = linker.question_needs_image(q_text)
                    if needs_img:
                        print(f"      Q{match} needs image: '{pattern}'")
                        
                        # Check if there's an image on this page
                        if page_num + 1 in images_by_page:
                            print(f"      ✅ Image available on this page!")
                        else:
                            print(f"      ❌ No image on this page")
    
    doc.close()


def cmd_export(args):
    """Export questions with images to HTML"""
    from storage.json_storage import QuestionStorage
    
    storage = QuestionStorage()
    output_path = Path(args.output) if args.output else Path("data/questions_with_images.html")
    
    print(f"\n📤 Exporting questions to HTML...")
    count = storage.export_with_images_html(output_path, limit=args.limit)
    
    print(f"✅ Exported {count} questions to {output_path}")
    print(f"\n   Open this file in a browser to view!")


def cmd_serve(args):
    """Start web interface"""
    import subprocess
    
    print("🚀 Starting FMGE Practice Engine...")
    print(f"   Open http://localhost:{args.port} in your browser")
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "ui/app.py",
        "--server.port", str(args.port)
    ])


def main():
    import re  # Need for diagnose command
    
    parser = argparse.ArgumentParser(description="FMGE Practice & Analysis Engine")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect PDF formats')
    detect_parser.add_argument('--input-dir', '-i', help='PDF directory')
    detect_parser.set_defaults(func=cmd_detect)
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process PDFs')
    process_parser.add_argument('--input-dir', '-i', help='PDF directory')
    process_parser.add_argument('--append', action='store_true', help='Append to existing')
    process_parser.add_argument('--no-images', action='store_true', help='Skip image extraction')
    process_parser.set_defaults(func=cmd_process)
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    # View command
    view_parser = subparsers.add_parser('view', help='View questions')
    view_parser.add_argument('--show-linked', action='store_true', help='Show questions with images')
    view_parser.add_argument('--show-missing', action='store_true', help='Show questions needing images')
    view_parser.set_defaults(func=cmd_view)
    
    # Diagnose command
    diagnose_parser = subparsers.add_parser('diagnose', help='Diagnose image issues in a PDF')
    diagnose_parser.add_argument('pdf', help='Path to PDF file')
    diagnose_parser.set_defaults(func=cmd_diagnose)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export to HTML')
    export_parser.add_argument('--output', '-o', help='Output file path')
    export_parser.add_argument('--limit', '-l', type=int, default=100, help='Max questions')
    export_parser.set_defaults(func=cmd_export)
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start web UI')
    serve_parser.add_argument('--port', type=int, default=8501)
    serve_parser.set_defaults(func=cmd_serve)
    
    args = parser.parse_args()
    
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()