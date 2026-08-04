import re

def search_app():
    with open(r'd:\MIDWAY\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "function App(" in line or "const App = " in line:
            print(f"App component found at line {i+1}: {line.strip()}")
            return i+1
            
if __name__ == "__main__":
    search_app()
