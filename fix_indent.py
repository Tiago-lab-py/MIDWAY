import sys

filepath = r"D:\MIDWAY\midway\api\routes\executivo_9282.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_dec_fec = False
for i, line in enumerate(lines):
    if "def dec_fec" in line:
        in_dec_fec = True
        
    if in_dec_fec:
        if i >= 113 and i <= 514:
            new_lines.append("    " + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("File fixed!")
