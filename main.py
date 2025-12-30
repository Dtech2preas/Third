from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.viewclass import ViewClass
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform
import json
import os
import threading
import time  # Fix: Added missing import
import extractor
import downloader

# ============================================
# WIDGETS
# ============================================

class SelectableLabel(RecycleDataViewBehavior, Label):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(SelectableLabel, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

class SelectableRecycleBoxLayout(FocusBehavior, RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''
    pass

class AnimeButton(Button):
    pass

# ============================================
# SCREENS
# ============================================

class SearchScreen(Screen):
    def search_anime(self):
        query = self.ids.search_input.text.strip()
        if not query:
            return
            
        first_letter = query[0].upper()
        # Handle cases where first char is not a letter
        if not first_letter.isalpha():
            first_letter = "Other" # Assuming you might have a file for non-letters or handle differently
            
        filename = f"anime_index/anime_{first_letter}.json"
        
        results = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    # Filter
                    for anime in data.get('anime', []):
                        if query.lower() in anime['title'].lower():
                            results.append(anime)
            except Exception as e:
                print(f"Error reading JSON: {e}")
        
        self.display_results(results)

    def display_results(self, results):
        self.ids.results_list.data = [
            {'text': anime['title'], 'anime_data': anime} for anime in results
        ]

    def on_result_selected(self, anime_data):
        # Navigate to Episode Screen
        app = App.get_running_app()
        app.root.get_screen('episodes').load_episodes(anime_data)
        app.root.current = 'episodes'

class EpisodeScreen(Screen):
    anime_title = StringProperty("")
    
    def load_episodes(self, anime_data):
        self.anime_title = anime_data['title']
        self.ids.episode_list.data = [
            {'text': f"Episode {ep['number']}", 'ep_data': ep} for ep in anime_data['episodes']
        ]
    
    def on_episode_selected(self, ep_data):
        # Start Download
        iframe_url = ep_data.get('iframe_url')
        if iframe_url:
            self.show_download_popup(ep_data['title'], iframe_url)

    def show_download_popup(self, title, url):
        content = BoxLayout(orientation='vertical')
        self.status_label = Label(text="Initializing...")
        content.add_widget(self.status_label)
        
        self.popup = Popup(title=f"Downloading {title}",
                      content=content,
                      size_hint=(0.8, 0.4),
                      auto_dismiss=False)
        self.popup.open()
        
        # Run in thread
        threading.Thread(target=self.run_download, args=(url,)).start()

    def run_download(self, kwik_url):
        def update_status(msg):
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', msg))

        update_status("Extracting Link...")
        data = extractor.get_kwik_data(kwik_url)
        
        if not data:
            update_status("Extraction Failed!")
            Clock.schedule_once(lambda dt: self.popup.dismiss(), 3)
            return

        update_status("Downloading... 0%")
        
        def progress_callback(percent):
            update_status(f"Downloading... {percent}%")

        # Determine download path (Android friendly)
        if platform == 'android':
            from android.storage import primary_external_storage_path
            dir = primary_external_storage_path() + '/Download'
            if not os.path.exists(dir):
                dir = primary_external_storage_path()
        else:
            dir = '.'
            
        output_file = os.path.join(dir, f"video_{int(time.time())}.mp4")

        success = downloader.download_stream_pure_python(
            data['url'],
            output_file,
            {"User-Agent": data['user_agent'], "Referer": data['referer']},
            data['cookies'],
            callback=progress_callback
        )
        
        if success:
            update_status(f"Saved to: {output_file}")
        else:
            update_status("Download Failed.")
            
        # Close popup after delay
        Clock.schedule_once(lambda dt: self.popup.dismiss(), 3)

    def go_back(self):
        App.get_running_app().root.current = 'search'

# ============================================
# APP
# ============================================

class AnimeApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SearchScreen(name='search'))
        sm.add_widget(EpisodeScreen(name='episodes'))
        return sm

    def on_start(self):
        # Request Android Permissions at Runtime
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE, 
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])

if __name__ == '__main__':
    AnimeApp().run()
