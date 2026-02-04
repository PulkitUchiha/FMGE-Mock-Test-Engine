Step 1: Detect Formats First
Bash

python main.py detect --input-dir "D:\test\data\raw_pdfs"
This will show you what formats are detected in each PDF.

Step 2: Process All PDFs
Bash

python main.py process --input-dir "D:\test\data\raw_pdfs"
Step 3: Check Review Queue (for image-based questions)
Bash

python main.py review --export review_items.md
Step 4: View Statistics
Bash

python main.py stats