def search():
    with open("d:/MIDWAY/frontend/src/App.jsx", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "produtoCockpit" in line or "suspeitas" in line.lower() or "indispon" in line.lower():
            if "fonte anal" in line.lower() or "indispon" in line.lower() or "Cockpit:" in line:
                print(f"Line {i+1}: {line.strip()}")
                
if __name__ == "__main__":
    search()
