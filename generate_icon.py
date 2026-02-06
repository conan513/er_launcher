from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

def draw_ring(draw, center_x, center_y, radius, width, color):
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], outline=color, width=width)

def create_icon():
    size = 512
    # Dark charcoal background
    img = Image.new("RGBA", (size, size), (13, 13, 13, 255))
    draw = ImageDraw.Draw(img)
    
    cx, cy = size // 2, size // 2
    gold = "#d4af37"
    bright_gold = "#ffdf00"
    
    # Draw Vertical Line (The main stem)
    draw.line([cx, cy - 200, cx, cy + 180], fill=gold, width=8)
    
    # Draw the specific interlocking ring structure
    # Top Ring
    draw_ring(draw, cx, cy - 100, 70, 6, gold)
    
    # Middle Pair (overlapping horizontally)
    draw_ring(draw, cx - 40, cy, 85, 6, gold)
    draw_ring(draw, cx + 40, cy, 85, 6, gold)
    
    # Bottom Arc / Large Ring
    # We want a large arc at the bottom
    draw.arc([cx - 200, cy + 50, cx + 200, cy + 350], start=200, end=340, fill=gold, width=10)
    
    # Add a crossbar near the top
    draw.line([cx - 50, cy - 160, cx + 50, cy - 160], fill=gold, width=6)
    
    # Apply a slight glow effect
    # We can do this by blurring a copy and pasting it under
    glow = img.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.alpha_composite(glow, img)
    
    # Save as PNG
    img.save("app_icon.png")
    
    # Convert to ICO
    img_ico = img.resize((256, 256), Image.Resampling.LANCZOS)
    img_ico.save("app_icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

if __name__ == "__main__":
    create_icon()
