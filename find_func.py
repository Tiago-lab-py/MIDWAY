def test():
    with open("d:/MIDWAY/midway/api/routes/produto.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if "_painel_suspeitas_ra" in line:
                print(f"Line {i+1}: {line.strip()}")
                
if __name__ == "__main__":
    test()
