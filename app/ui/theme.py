class UITheme:


    def get_theme(self,name):
        """Return a message theme dict by name (e.g., 'message_info', 'message_error')."""
        return getattr(self, name, None)
    
    def __init__(self, fonts):
        self.fonts = fonts
        self.colors = {
            "background": "white",
            "primary": "blue",
            "secondary": "gray",
            "error": "red",
            "text": "black",
            "highlight": "green",
        }
        self.layout = {
            "screen_width": 480,
            "screen_height": 320,
            "padding": 20,
            "line_height": 25,
            "title_y": 10,
            "company_y": 90,
            "product_y": 130,
        }

        self.message_error = {
            "background": "#FF0000",
        }

        self.message_info = {
            "background": "#FFFFFF",
        }

        _volume_bar = {"width": 15, "height": 200}
        
        _home_layout = {
            "screen_title": {"x": self.layout["padding"], "y": 10},
            "album_image": {"x": 20, "y": 50, "width": 440, "height": 240},
            "volume_bar": {"x": 20, "y": 300, "width": 440, "height": 15},
            "status_icon": {"x": 20, "y": 320, "width": 30, "height": 30},
            "artist_name": {"x": 20, "y": 60, "width": 440, "height": 30},
            "album_name_year": {"x": 20, "y": 90, "width": 440, "height": 30},
            "track_title": {"x": 20, "y": 150, "width": 440, "height": 30},
        }

        self.home_layout = {
            "screen_title": {"x": self.layout["padding"], "y": 10},
            "title": {"font": self.fonts["title"], "size": 24, "color": self.colors["text"], "y": 10},
            "volume_bar":  {"width": 15, "height": 200},
            "status_icon": {"size": 30}, 
            "album_image": {"size": 180},
            "content": {"y": 60}
        }
