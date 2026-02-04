"""
PDF Diagnostic Tool
Analyzes PDF content to understand the actual format
"""

import fitz  # PyMuPDF
from pathlib import Path
import re

def diagnose_pdf(pdf_path: Path, sample_pages: int = 3):
    """Analyze a PDF to understand its structure"""
    
    print(f"\n{'='*70}")
    print(f"📄 ANALYZING: {pdf_path.name}")
    print(f"{'='*70}")
    
    try:
        doc = fitz.open(pdf_path)
        print(f"Total pages: {len(doc)}")
        
        # Analyze first few pages
        for page_num in range(min(sample_pages, len(doc))):
            page = doc[page_num]
            text = page.get_text("text")
            
            print(f"\n{'─'*50}")
            print(f"📖 PAGE {page_num + 1}")
            print(f"{'─'*50}")
            
            # Show first 2000 characters
            preview = text[:2000]
            print(preview)
            
            if len(text) > 2000:
                print(f"\n... [{len(text) - 2000} more characters]")
            
            # Try to identify patterns
            print(f"\n🔍 PATTERN ANALYSIS:")
            
            # Look for question-like patterns
            patterns_to_check = [
                (r'\d{1,3}[\.\)\:]', "Number patterns (1. or 1) or 1:)"),
                (r'Q\s*\d+', "Q1, Q 1, Q.1 patterns"),
                (r'Question\s*\d+', "Question 1 patterns"),
                (r'\[\d+\]', "[1] patterns"),
                (r'^\s*[A-Da-d][\.\)\:]', "Option patterns (A. B. etc)"),
                (r'\([A-Da-d]\)', "(A) (B) patterns"),
                (r'Ans(?:wer)?', "Answer markers"),
                (r'Explanation', "Explanation markers"),
                (r'(?:correct|right)\s*(?:answer|option)', "Correct answer markers"),
            ]
            
            for pattern, description in patterns_to_check:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    unique_matches = list(set(matches[:10]))
                    print(f"  ✅ {description}: {len(matches)} matches")
                    print(f"     Examples: {unique_matches[:5]}")
                else:
                    print(f"  ❌ {description}: No matches")
        
        doc.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


def analyze_all_pdfs(directory: Path):
    """Analyze all PDFs in a directory"""
    
    pdf_files = list(directory.glob("*.pdf"))
    print(f"\n🔍 Found {len(pdf_files)} PDF files\n")
    
    for pdf_path in pdf_files[:3]:  # Analyze first 3 PDFs
        diagnose_pdf(pdf_path)
    
    print(f"\n{'='*70}")
    print("📊 SUMMARY: Check the patterns above to understand your PDF format")
    print("Then update the parser patterns accordingly")
    print(f"{'='*70}")


def extract_sample_questions(pdf_path: Path, num_samples: int = 5):
    """Try to manually identify question boundaries"""
    
    print(f"\n{'='*70}")
    print(f"🔬 DEEP ANALYSIS: {pdf_path.name}")
    print(f"{'='*70}")
    
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for page in doc:
        full_text += page.get_text("text") + "\n"
    
    doc.close()
    
    # Try different splitting strategies
    print("\n📝 Trying to find question blocks...")
    
    # Strategy 1: Look for numbered items
    numbered_pattern = r'(\d{1,3})\s*[\.\)\:]\s*(.{50,500}?)(?=\d{1,3}\s*[\.\)\:]|$)'
    matches = re.findall(numbered_pattern, full_text, re.DOTALL)
    
    if matches:
        print(f"\n✅ Found {len(matches)} potential questions using numbered pattern")
        print("\nFirst 3 samples:")
        for i, (num, text) in enumerate(matches[:3]):
            print(f"\n--- Question {num} ---")
            print(text[:300].strip())
    else:
        print("❌ Numbered pattern didn't work")
    
    # Strategy 2: Look for lines starting with numbers
    lines = full_text.split('\n')
    question_lines = []
    
    for i, line in enumerate(lines):
        if re.match(r'^\s*\d{1,3}\s*[\.\)\:]', line):
            # Get this line and next few lines
            context = '\n'.join(lines[i:i+6])
            question_lines.append((i, context))
    
    if question_lines:
        print(f"\n✅ Found {len(question_lines)} lines starting with numbers")
        print("\nFirst 3 samples:")
        for line_num, context in question_lines[:3]:
            print(f"\n--- Line {line_num} ---")
            print(context[:400])
    
    # Show raw text structure
    print("\n" + "="*50)
    print("📄 RAW TEXT STRUCTURE (first 5000 chars):")
    print("="*50)
    print(full_text[:5000])


if __name__ == "__main__":
    # Change this path to your PDF directory
    pdf_dir = Path(r"D:\test\data\raw_pdfs")
    
    print("🔍 PDF DIAGNOSTIC TOOL")
    print("This will help identify the actual format of your PDFs\n")
    
    # Analyze all PDFs
    analyze_all_pdfs(pdf_dir)
    
    # Deep analysis of one PDF
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if pdf_files:
        extract_sample_questions(pdf_files[0])