"""Compose operator + system screenshots side by side. python side_by_side.py <operator.png> <system.png> <out.png>"""
import sys
from PIL import Image, ImageDraw

op, sy = Image.open(sys.argv[1]), Image.open(sys.argv[2])
H = max(op.height, sy.height)
out = Image.new("RGB", (op.width + sy.width + 12, H + 24), (20, 23, 28))
out.paste(op, (0, 24)); out.paste(sy, (op.width + 12, 24))
d = ImageDraw.Draw(out)
d.text((8, 6), "OPERATOR window (?role=operator) - person + WASD", fill=(220, 220, 220))
d.text((op.width + 20, 6), "SYSTEM window (?role=system) - camera pixels only", fill=(220, 220, 220))
out.save(sys.argv[3])
