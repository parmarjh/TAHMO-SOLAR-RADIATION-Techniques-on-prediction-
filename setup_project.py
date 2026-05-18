import os
import shutil

def setup_product_structure():
    print("🚀 Initializing TAHMO Project Product-Wise Automation Setup...")
    
    # 1. Define standard product directories to create
    directories = [
        "data",
        "src",
        "notebooks",
        "docs",
        "web",
        "outputs"
    ]
    
    for folder in directories:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"  [+] Created directory: {folder}/")
        else:
            print(f"  [~] Directory already exists: {folder}/")
            
    # 2. Map existing files in flat root to their product folders
    file_mapping = {
        # Data files
        "Train.csv": "data/Train.csv",
        "Test.csv": "data/Test.csv",
        "SampleSubmission.csv": "data/SampleSubmission.csv",
        "dataset_data_dictionary.csv": "data/dataset_data_dictionary.csv",
        
        # Source Scripts
        "tahmo_radiation_solution.py": "src/tahmo_radiation_solution.py",
        "tahmo_solution_fast.py": "src/tahmo_solution_fast.py",
        "ADVANCED_TECHNIQUES.py": "src/ADVANCED_TECHNIQUES.py",
        
        # Jupyter Notebooks
        "tahmo_starter_notebook.ipynb": "notebooks/tahmo_starter_notebook.ipynb",
        
        # Documentations
        "00_START_HERE.md": "docs/00_START_HERE.md",
        "QUICK_START.md": "docs/QUICK_START.md",
        "SOLUTION_GUIDE.md": "docs/SOLUTION_GUIDE.md",
        "analysis.txt": "docs/analysis.txt",
        
        # Web Interactive App
        "dashboard.html": "web/dashboard.html"
    }
    
    print("\n📦 Re-routing files into product-wise folders:")
    for filename, target_path in file_mapping.items():
        if os.path.exists(filename):
            try:
                shutil.move(filename, target_path)
                print(f"  [→] Moved: {filename}  ⇒  {target_path}")
            except Exception as e:
                print(f"  [!] Failed to move {filename}: {e}")
        else:
            print(f"  [-] Skipped (file not in root): {filename}")
            
    # 3. Update local gitignore paths to align with new data directory
    gitignore_path = ".gitignore"
    if os.path.exists(gitignore_path):
        print("\n🔧 Updating .gitignore with new product-wise paths...")
        with open(gitignore_path, "r") as f:
            lines = f.readlines()
            
        updated_lines = []
        for line in lines:
            # Upgrade raw CSV names to point to data/ folder
            if line.strip() in ["Train.csv", "Test.csv", "SampleSubmission.csv"]:
                updated_lines.append(f"data/{line}")
            else:
                updated_lines.append(line)
                
        with open(gitignore_path, "w") as f:
            f.writelines(updated_lines)
        print("  [+] Refactored .gitignore paths successfully!")

    # 4. Generate Visual Directory Map
    print("\n✨ Product-Wise Setup Complete! Final Workspace Architecture:")
    print("==========================================================")
    print("TAHMO-SOLAR-RADIATION/")
    print("├── .gitignore")
    print("├── README.md")
    print("├── setup_project.py")
    print("├── data/")
    print("│   ├── Train.csv")
    print("│   ├── Test.csv")
    print("│   ├── SampleSubmission.csv")
    print("│   └── dataset_data_dictionary.csv")
    print("├── src/")
    print("│   ├── tahmo_radiation_solution.py")
    print("│   ├── tahmo_solution_fast.py")
    print("│   └── ADVANCED_TECHNIQUES.py")
    print("├── notebooks/")
    print("│   └── tahmo_starter_notebook.ipynb")
    print("├── docs/")
    print("│   ├── 00_START_HERE.md")
    print("│   ├── QUICK_START.md")
    print("│   ├── SOLUTION_GUIDE.md")
    print("│   └── analysis_results.md (in brain log)")
    print("├── web/")
    print("│   └── dashboard.html")
    print("└── outputs/")
    print("    └── [submission.csv generated here]")
    print("==========================================================")

if __name__ == "__main__":
    setup_product_structure()
