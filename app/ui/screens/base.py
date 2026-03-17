import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)

class Screen:
    def __init__(self, width=480, height=320):
        self.width = width
        self.height = height

    def draw(self, draw_context, fonts, player=None):
        pass
    
class Element():
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.box = (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def rect_coords(self):
        """Return rectangle coordinates in PIL format: [(x1, y1), (x2, y2)]"""
        return [(self.x, self.y), (self.x + self.width, self.y + self.height)]

    @property
    def x2(self):
        """Return the x2 coordinate of the element."""
        return self.x + self.width

    @property
    def y2(self):
        """Return the y2 coordinate of the element."""
        return self.y + self.height

    def draw(self, draw_context):
        raise NotImplementedError("Subclasses must implement this method")

class RectElement(Element):
    def __init__(self, x, y, width, height, fill):
        super().__init__(x, y, width, height)
        self.fill = fill

    def draw(self, draw_context):
        draw_context.rectangle((self.x, self.y, self.x + self.width, self.y + self.height), fill=self.fill)

class TextElement(Element):
    def __init__(self, x, y, width, height, text, font):
        super().__init__(x, y, width, height)
        self.text = text
        self.font = font

    def draw(self, draw_context):
        lines = self._wrap_text(draw_context)
        text_x = self.x
        text_y = self.y
        for line in lines:
            bbox = draw_context.textbbox((0, 0), line, font=self.font)
            text_height = bbox[3] - bbox[1]
            draw_context.text((text_x, text_y), line, fill="black", font=self.font)
            text_y += text_height  # Move down for next line

    def _wrap_text(self, draw_context):
        """Wrap self.text so each line fits within self.width."""
        words = self.text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = draw_context.textbbox((0, 0), test_line, font=self.font)
            line_width = bbox[2] - bbox[0]
            if line_width <= self.width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines        

class ImageElement(Element):
    """
    Unified image element that handles all types of image loading:
    - Album covers (with fallback logic)
    - Icons (from config definitions)
    - No image placeholder when no parameters provided
    """
    
    def __init__(self, x, y, width, height, iconname=None, album_id=None, size=None):
        """
        Initialize ImageElement with convention-based image loading.
        
        Args:
            x, y, width, height: Element positioning and sizing
            iconname: Icon name for loading from static_files (mutually exclusive with album_id)
            album_id: Album ID for loading album cover (mutually exclusive with iconname)
            size: Size for album covers (defaults to 180 if album_id provided)
        """
        super().__init__(x, y, width, height)
        self.iconname = iconname
        self.album_id = album_id
        self.size = size
        self.image = None
        self._load_image()

    def _load_image(self):
        """Load image based on convention-based parameters."""
        try:
            # Check for conflicting parameters
            if self.iconname is not None and self.album_id is not None:
                logger.warning(f"ImageElement: Both iconname='{self.iconname}' and album_id='{self.album_id}' provided. This is not allowed.")
                self.image = self._load_no_image_placeholder()
                return
            
            # Load based on parameters provided
            if self.album_id is not None:
                # Album cover with size (default 180)
                cover_size = self.size if self.size is not None else 180
                self.image = self._load_album_cover(self.album_id, cover_size)
            elif self.iconname is not None:
                # Icon from static files
                self.image = self._load_icon(self.iconname)
            else:
                # No parameters - return placeholder
                self.image = self._load_no_image_placeholder()
                
        except Exception as e:
            logger.error(f"Failed to load image (iconname={self.iconname}, album_id={self.album_id}): {e}")
            self.image = self._load_no_image_placeholder()

    def _load_from_path(self, path):
        """Load image from file path."""
        if not path or not os.path.exists(path):
            return None
        
        logger.debug(f"Loading image from path: {path}")
        return Image.open(path).convert("RGBA")

    def _load_album_cover(self, album_id, size=180):
        """Load album cover with fallback logic."""
        if not album_id:
            return self._load_no_image_placeholder()
            
        from app.config import config
        import os
        
        try:
            base = config.STATIC_FILE_PATH
            # Candidate paths for album-specific cover
            candidates = [
                os.path.join(base, 'covers', str(album_id), f'cover-{size}.webp'),
                os.path.join(base, 'covers', str(album_id), f'cover-{size}.jpg'),
            ]
            # Fallback to default placeholder
            candidates += [
                os.path.join(base, 'covers', '_default', f'cover-{size}.webp'),
                os.path.join(base, 'covers', '_default', f'cover-{size}.jpg'),
            ]
            
            for path in candidates:
                return self._load_from_path(path)
                    
        except Exception as e:
            logger.error(f"Failed to load album cover for {album_id}: {e}")
        
        return self._load_no_image_placeholder()

    def _load_icon(self, icon_name):
        """Load icon from config definitions."""
        from app.config import config
        
        icon_path = config.get_icon_path(icon_name)
        if icon_path:
            return self._load_from_path(icon_path)
        return self._load_no_image_placeholder()

    def _load_no_image_placeholder(self):
        """Create a placeholder image for when no image is available."""
        try:
            # Create a simple placeholder image
            placeholder = Image.new('RGBA', (self.width, self.height), (240, 240, 240, 255))
            return placeholder
        except Exception as e:
            logger.error(f"Failed to create placeholder image: {e}")
            return None

    def _resize_image(self, image):
        """Resize image to fit element dimensions if needed."""
        if not image:
            return None
            
        # Resize if image dimensions don't match element dimensions
        if image.size[0] != self.width or image.size[1] != self.height:
            return image.resize((self.width, self.height), resample=Image.LANCZOS)
        return image

    def draw(self, draw_context, canvas):
        """Draw the image element on the canvas."""
        if self.image is not None:
            try:
                # Resize image if needed
                display_image = self._resize_image(self.image)
                mask = display_image if display_image.mode == 'RGBA' else None
                canvas.paste(display_image, (self.x, self.y), mask)
            except Exception as e:
                logger.error(f"Error displaying image: {e}")
                self._draw_error_placeholder(draw_context)
        else:
            self._draw_error_placeholder(draw_context)

    def _draw_error_placeholder(self, draw_context):
        """Draw error placeholder when image loading fails."""
        draw_context.rectangle(self.rect_coords, outline="black", fill=None)
        # Center error text
        error_text = "No Image"
        bbox = draw_context.textbbox((0, 0), error_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = self.x + (self.width - text_width) // 2
        text_y = self.y + (self.height - text_height) // 2
        draw_context.text((text_x, text_y), error_text, fill="black")


class MenuItemElement(Element):
    """Element for rendering individual menu items with optional selection highlight"""
    def __init__(self, x, y, width, height, text, font, is_selected=False, highlight_color="#24AC5F"):
        super().__init__(x, y, width, height)
        self.text = text
        self.font = font
        self.is_selected = is_selected
        self.highlight_color = highlight_color

    def draw(self, draw_context):
        # Draw background highlight if selected
        if self.is_selected:
            draw_context.rectangle((self.x, self.y, self.x + self.width, self.y + self.height), 
                                 fill=self.highlight_color)
            text_color = "white"
        else:
            text_color = "black"
        
        # Calculate text positioning
        bbox = draw_context.textbbox((0, 0), self.text, font=self.font)
        text_height = bbox[3] - bbox[1]
        
        # Left align with padding, vertically center
        text_x = self.x + 10  # 10px left padding
        text_y = self.y + (self.height - text_height) // 2
        
        draw_context.text((text_x, text_y), self.text, fill=text_color, font=self.font)


class MenuHeaderElement(Element):
    """Element for rendering menu header with breadcrumb"""
    def __init__(self, x, y, width, height, title, font, background_color="white", text_color="black"):
        super().__init__(x, y, width, height)
        self.title = title
        self.font = font
        self.background_color = background_color
        self.text_color = text_color

    def draw(self, draw_context):
        # Draw header background
        draw_context.rectangle((self.x, self.y, self.x + self.width, self.y + self.height), 
                             fill=self.background_color)
        
        # Draw bottom border line
        draw_context.line([(self.x, self.y + self.height - 1), 
                          (self.x + self.width, self.y + self.height - 1)], 
                         fill="gray", width=1)
        
        # Calculate text positioning
        bbox = draw_context.textbbox((0, 0), self.title, font=self.font)
        text_height = bbox[3] - bbox[1]
        
        # Left align with padding, vertically center
        text_x = self.x + 10
        text_y = self.y + (self.height - text_height) // 2
        
        draw_context.text((text_x, text_y), self.title, fill=self.text_color, font=self.font)

