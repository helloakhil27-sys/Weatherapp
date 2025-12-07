"""
spaceweather_enhanced_ui.py
Centered SpaceX/Tesla-inspired weather + AQI app with:
 - IQAir (AirVisual) for AQI
 - OpenWeatherMap for weather + pollutant breakdown & geocoding
 - Animated AQI color transitions
 - Animated dynamic gradient background (simulated blur via layered translucent rectangles)
 - Animated weather icons (emoji-based, subtle motion)
 - Bottom navigation bar (Weather / AQI / Forecast)

Requirements:
    pip install kivy plyer requests
Replace OWM_API_KEY and IQAIR_API_KEY with your keys.
"""

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import (
    StringProperty, ListProperty, NumericProperty, BooleanProperty
)
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen

import threading, requests, time

# optional plyer gps
try:
    from plyer import gps
    PLYER_GPS_AVAILABLE = True
except Exception:
    PLYER_GPS_AVAILABLE = False

# ----- CONFIG -----
OWM_API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"
IQAIR_API_KEY = "YOUR_IQAIR_API_KEY"
UPDATE_INTERVAL = 5 * 60  # seconds

Window.size = (1000, 700)  # desktop preview size (doesn't force mobile)

KV = f'''
#:import dp kivy.metrics.dp

<GradientLayer@Widget>:
    color_a: 0, 0, 0, 1
    color_b: 0, 0, 0, 0
    canvas:
        Color:
            rgba: self.color_a
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: self.color_b
        Rectangle:
            pos: self.pos
            size: self.size

<WeatherIcon@Label>:
    font_size: dp(44)
    halign: 'center'
    valign: 'middle'
    size_hint: None, None
    size: dp(64), dp(64)

# root layout
FloatLayout:
    id: rootfl

    # animated layered gradient background (center column floats above)
    GradientLayer:
        id: bg0
        color_a: app.bg_a
        color_b: app.bg_b
        size: rootfl.size
        pos: rootfl.pos

    # translucent overlay to simulate soft blur/veil
    GradientLayer:
        id: overlay
        color_a: (0,0,0,0.15)
        color_b: (0,0,0,0.15)
        size: rootfl.size
        pos: rootfl.pos

    # centered app column
    BoxLayout:
        orientation: 'vertical'
        size_hint: None, 1
        width: rootfl.width if rootfl.width < dp(420) else dp(420)
        pos_hint: {{'center_x': 0.5}}
        padding: dp(12)
        spacing: dp(12)

        canvas.before:
            Color:
                rgba: (0,0,0,0)
            Rectangle:
                pos: self.pos
                size: self.size

        # header + search
        BoxLayout:
            size_hint_y: None
            height: dp(72)
            spacing: dp(8)

            BoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.6
                Label:
                    text: "SPACE WEATHER"
                    bold: True
                    font_size: '18sp'
                    color: (1,1,1,0.95)
                    halign: 'left'
                    valign: 'middle'
                Label:
                    text: "Realtime weather • AQI"
                    font_size: '10sp'
                    color: (1,1,1,0.55)
                    halign: 'left'
                    valign: 'middle'

            BoxLayout:
                size_hint_x: 0.4
                spacing: dp(6)
                TextInput:
                    id: city_input
                    hint_text: "Enter city"
                    multiline: False
                    size_hint_x: 0.7
                    background_normal: ''
                    background_color: (1,1,1,0.04)
                    foreground_color: (1,1,1,0.95)
                    padding: [dp(8), dp(8), dp(8), dp(8)]
                    on_text_validate: app.search_city(self.text)
                Button:
                    text: 'Search'
                    size_hint_x: 0.3
                    on_release: app.search_city(city_input.text)
                    background_normal: ''
                    background_color: (1,1,1,0.04)
                    color: (1,1,1,0.95)

        # screen manager (Weather, AQI, Forecast)
        ScreenManager:
            id: sm
            size_hint_y: None
            height: root.fl_height if hasattr(root, 'fl_height') else root.height - dp(200)

            Screen:
                name: 'weather'

                BoxLayout:
                    orientation: 'vertical'
                    spacing: dp(12)

                    # temp card with animated icon
                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: dp(240)
                        padding: dp(20)
                        spacing: dp(8)
                        canvas.before:
                            Color:
                                rgba: (0.06,0.07,0.09,1)
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12,]

                        BoxLayout:
                            orientation: 'horizontal'
                            size_hint_y: None
                            height: dp(96)
                            spacing: dp(12)

                            BoxLayout:
                                orientation: 'vertical'
                                size_hint_x: .25
                                WeatherIcon:
                                    id: weather_icon
                                    text: app.weather_icon
                                    font_size: dp(42)
                                    color: (1,1,1,1)
                            BoxLayout:
                                orientation: 'vertical'
                                Label:
                                    id: temp_label
                                    text: app.temp_display
                                    font_size: '64sp'
                                    bold: True
                                    color: (1,1,1,1)
                                Label:
                                    id: cond_label
                                    text: app.condition_display
                                    font_size: '16sp'
                                    color: (1,1,1,0.85)

                        BoxLayout:
                            size_hint_y: None
                            height: dp(36)
                            spacing: dp(8)
                            Label:
                                text: app.location_display
                                font_size: '14sp'
                                color: (1,1,1,0.7)
                            Label:
                                text: app.updated_display
                                font_size: '12sp'
                                color: (1,1,1,0.5)

                    # details row
                    BoxLayout:
                        orientation: 'horizontal'
                        size_hint_y: None
                        height: dp(140)
                        spacing: dp(12)
                        canvas.before:
                            Color:
                                rgba: (0.06,0.07,0.09,1)
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12,]

                        GridLayout:
                            cols: 3
                            rows: 2
                            row_default_height: dp(40)
                            row_force_default: True
                            spacing: dp(8)
                            padding: dp(12)
                            Label:
                                text: 'Humidity'
                                font_size: '14sp'
                                color: (1,1,1,0.8)
                            Label:
                                text: 'Wind'
                                font_size: '14sp'
                                color: (1,1,1,0.8)
                            Label:
                                text: 'Pressure'
                                font_size: '14sp'
                                color: (1,1,1,0.8)
                            Label:
                                text: app.humidity_display
                                font_size: '20sp'
                                color: (1,1,1,0.95)
                            Label:
                                text: app.wind_display
                                font_size: '20sp'
                                color: (1,1,1,0.95)
                            Label:
                                text: app.pressure_display
                                font_size: '20sp'
                                color: (1,1,1,0.95)

            Screen:
                name: 'aqi'

                BoxLayout:
                    orientation: 'vertical'
                    spacing: dp(12)

                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: dp(170)
                        padding: dp(14)
                        spacing: dp(8)
                        canvas.before:
                            Color:
                                rgba: (0.06,0.07,0.09,1)
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12,]

                        BoxLayout:
                            spacing: dp(12)
                            Label:
                                text: app.aqi_display
                                font_size: '48sp'
                                bold: True
                                color: app.aqi_color
                            BoxLayout:
                                orientation: 'vertical'
                                Label:
                                    text: app.aqi_category
                                    font_size: '16sp'
                                    color: (1,1,1,0.9)
                                Label:
                                    text: app.aqi_message
                                    font_size: '12sp'
                                    color: (1,1,1,0.7)

                        GridLayout:
                            cols: 3
                            size_hint_y: None
                            height: dp(50)
                            spacing: dp(6)
                            Label:
                                text: 'PM2.5'
                                color: (1,1,1,0.75)
                            Label:
                                text: 'PM10'
                                color: (1,1,1,0.75)
                            Label:
                                text: 'Main Pollutant'
                                color: (1,1,1,0.75)

                            Label:
                                text: app.pm25_display
                                color: (1,1,1,0.95)
                            Label:
                                text: app.pm10_display
                                color: (1,1,1,0.95)
                            Label:
                                text: app.main_pollutant
                                color: (1,1,1,0.9)

            Screen:
                name: 'forecast'
                BoxLayout:
                    orientation: 'vertical'
                    spacing: dp(12)
                    Label:
                        text: 'Forecast (coming soon)'
                        font_size: '16sp'
                        color: (1,1,1,0.85)
                    Label:
                        text: 'You can add hourly and 7-day cards here.'
                        font_size: '12sp'
                        color: (1,1,1,0.6)

        # bottom navigation bar
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: (0,0,0,0)
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: 'Weather'
                on_release:
                    sm.current = 'weather'
                background_normal: ''
                background_color: (1,1,1,0.03)
                color: (1,1,1,0.95)
            Button:
                text: 'AQI'
                on_release:
                    sm.current = 'aqi'
                background_normal: ''
                background_color: (1,1,1,0.03)
                color: (1,1,1,0.95)
            Button:
                text: 'Forecast'
                on_release:
                    sm.current = 'forecast'
                background_normal: ''
                background_color: (1,1,1,0.03)
                color: (1,1,1,0.95)
'''

# ---------- Helper functions (same as before) ----------
def fetch_ip_location():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=6)
        if r.status_code == 200:
            j = r.json()
            loc = j.get("loc", "")
            if loc:
                lat_str, lon_str = loc.split(',')
                city = j.get("city", "")
                region = j.get("region", "")
                country = j.get("country", "")
                return float(lat_str), float(lon_str), city, region, country
    except Exception:
        pass
    return None

def owm_geocode_city(city_name, api_key):
    try:
        q = requests.utils.quote(city_name)
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={q}&limit=1&appid={api_key}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, list) and j:
            entry = j[0]
            return float(entry.get("lat")), float(entry.get("lon")), entry.get("name",""), entry.get("state",""), entry.get("country","")
    except Exception:
        pass
    return None

def fetch_weather(lat, lon, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    return r.json()

def fetch_openweather_pollution(lat, lon, api_key):
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        if "list" in j and j["list"]:
            return j["list"][0].get("components", {})
    except Exception:
        pass
    return None

def fetch_aqi_iqair(lat, lon, key):
    try:
        url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={key}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "success":
            pollution = j.get("data", {}).get("current", {}).get("pollution", {})
            aqi_val = pollution.get("aqius")
            main = pollution.get("mainus") or pollution.get("maincn") or ""
            return (int(aqi_val) if aqi_val is not None else None, main)
    except Exception:
        pass
    return (None, "")

def aqi_category_and_color(aqi_value):
    try:
        aqi = int(aqi_value)
    except Exception:
        return "Unknown", "No data", [1,1,1,1]
    if aqi <= 50:
        return "Good", "Air quality is satisfactory.", [0.2, 0.8, 0.2, 1]
    if aqi <= 100:
        return "Moderate", "Acceptable; sensitive groups should be cautious.", [0.95, 0.8, 0.2, 1]
    if aqi <= 150:
        return "Unhealthy for SG", "Sensitive groups may experience health effects.", [0.9, 0.55, 0.12, 1]
    if aqi <= 200:
        return "Unhealthy", "Everyone may begin to experience health effects.", [0.9, 0.2, 0.2, 1]
    if aqi <= 300:
        return "Very Unhealthy", "Health alert: emergency conditions possible.", [0.6, 0.15, 0.45, 1]
    return "Hazardous", "Health warnings of emergency conditions.", [0.5, 0.02, 0.02, 1]

# ---------- App ----------
class SpaceWeatherApp(App):
    # UI properties
    temp_display = StringProperty("--°C")
    condition_display = StringProperty("Loading…")
    location_display = StringProperty("Locating…")
    updated_display = StringProperty("")
    aqi_display = StringProperty("--")
    aqi_category = StringProperty("")
    aqi_message = StringProperty("")
    aqi_color = ListProperty([1,1,1,1])
    pm25_display = StringProperty("-- µg/m³")
    pm10_display = StringProperty("-- µg/m³")
    main_pollutant = StringProperty("--")
    humidity_display = StringProperty("--%")
    wind_display = StringProperty("-- m/s")
    pressure_display = StringProperty("-- hPa")
    weather_icon = StringProperty("☀️")  # emoji icon

    # animated background color properties (two color stops)
    bg_a = ListProperty([0.02, 0.03, 0.04, 1])
    bg_b = ListProperty([0.08, 0.09, 0.10, 1])

    # internal
    _last_fetch = None
    _last_aqi_color = ListProperty([1,1,1,1])

    def build(self):
        self.title = "SpaceWeather (Enhanced UI)"
        return Builder.load_string(KV)

    def on_start(self):
        # background gradient animation loop
        Clock.schedule_once(lambda dt: self._start_bg_animation(), 0.3)
        # initial fetch
        Clock.schedule_once(lambda dt: threading.Thread(target=self.update_all, daemon=True).start(), 0.5)
        # periodic updates
        Clock.schedule_interval(lambda dt: threading.Thread(target=self.update_all, daemon=True).start(), UPDATE_INTERVAL)

    # ---------------- Background gradient animation ----------------
    def _start_bg_animation(self):
        # define a few pleasing palettes (r,g,b,a)
        palettes = [
            ([0.02, 0.03, 0.04, 1], [0.08, 0.09, 0.10, 1]),  # dark
            ([0.03, 0.03, 0.06, 1], [0.12, 0.06, 0.08, 1]),  # dusk
            ([0.06, 0.03, 0.05, 1], [0.12, 0.08, 0.04, 1]),  # warm
            ([0.03, 0.05, 0.07, 1], [0.05, 0.12, 0.14, 1]),  # blue-green
        ]
        # cycle palettes every 10s with smooth animation
        def cycle(i=0):
            a, b = palettes[i % len(palettes)]
            anim = Animation(bg_a=a, bg_b=b, d=8.5, t='out_quad')
            anim.bind(on_complete=lambda *_: cycle(i+1))
            anim.start(self)
        cycle(0)

    # ---------------- AQI color animation ----------------
    @mainthread
    def _animate_aqi_color(self, target_color):
        """Animate the ListProperty aqi_color to target_color smoothly."""
        try:
            # use Animation on the aqi_color property (must be list)
            anim = Animation(aqi_color=target_color, d=0.9, t='out_cubic')
            anim.start(self)
        except Exception:
            self.aqi_color = target_color

    # ---------------- Animated icon behavior ----------------
    @mainthread
    def _animate_weather_icon(self, icon_text):
        """Set icon and start a gentle bounce/scale loop appropriate to icon type."""
        self.weather_icon = icon_text
        try:
            lbl = self.root.ids.weather_icon
            # cancel previous animations by starting a new one
            anim = Animation(font_size=dp(46), d=0.6) + Animation(font_size=dp(40), d=0.6)
            anim.repeat = True
            anim.start(lbl)
        except Exception:
            pass

    # ---------------- Location / search ----------------
    def search_city(self, city_text):
        if not city_text or not city_text.strip():
            return
        threading.Thread(target=self._search_and_fetch, args=(city_text.strip(),), daemon=True).start()

    def _search_and_fetch(self, city_text):
        res = owm_geocode_city(city_text, OWM_API_KEY)
        if not res:
            self._update_ui_from_data({"condition": "City not found"})
            return
        lat, lon, name, state, country = res
        self.update_all(lat_override=lat, lon_override=lon, city=name, region=state or country)

    def determine_location(self):
        if PLYER_GPS_AVAILABLE:
            try:
                location_event = {"lat": None, "lon": None}
                def on_location(**kwargs):
                    try:
                        location_event["lat"] = float(kwargs.get("lat"))
                        location_event["lon"] = float(kwargs.get("lon"))
                    except Exception:
                        pass
                def on_status(status):
                    pass
                gps.configure(on_location=on_location, on_status=on_status)
                gps.start(minTime=1000, minDistance=0)
                timeout = time.time() + 6
                while time.time() < timeout:
                    if location_event["lat"] and location_event["lon"]:
                        gps.stop()
                        return location_event["lat"], location_event["lon"], None, None, None
                    time.sleep(0.6)
                gps.stop()
            except Exception:
                pass
        return fetch_ip_location()

    # ---------------- UI update (mainthread) ----------------
    @mainthread
    def _update_ui_from_data(self, wdata):
        if not wdata:
            self.condition_display = "Unable to fetch data"
            return

        # temp
        temp = wdata.get('temp')
        if temp is None:
            new_temp_text = "--°C"
        else:
            try:
                new_temp_text = f"{float(temp):.0f}°C"
            except Exception:
                new_temp_text = f"{temp}°C"

        # update temp label without extra animation (we already have temp animation earlier)
        self.temp_display = new_temp_text

        # condition and location
        self.condition_display = wdata.get("condition", "—")
        city = wdata.get('city','')
        region = wdata.get('region','')
        self.location_display = f"{city} {region}".strip()
        self.updated_display = f"Updated {time.strftime('%H:%M:%S')}"

        # AQI and animate color
        aqi_val = wdata.get("aqi")
        if aqi_val is not None:
            self.aqi_display = str(aqi_val)
            cat, msg, target_color = aqi_category_and_color(aqi_val)
            self.aqi_category = cat
            self.aqi_message = msg
            # animate color transition
            self._animate_aqi_color(target_color)
        else:
            self.aqi_display = "--"
            self.aqi_category = "No AQI"
            self.aqi_message = "Data unavailable"
            self._animate_aqi_color([1,1,1,1])

        # pollutants
        pm25 = wdata.get("pm2_5")
        pm10 = wdata.get("pm10")
        self.pm25_display = (f"{float(pm25):.1f} µg/m³" if pm25 is not None else "-- µg/m³")
        self.pm10_display = (f"{float(pm10):.1f} µg/m³" if pm10 is not None else "-- µg/m³")
        self.main_pollutant = wdata.get("main_pollutant") or "--"

        # details
        humidity = wdata.get('humidity')
        try:
            if humidity is None or humidity == "--":
                self.humidity_display = "--%"
            else:
                h = int(float(humidity))
                if h < 0: h = 0
                if h > 100: h = min(h, 100)
                self.humidity_display = f"{h}%"
        except Exception:
            self.humidity_display = f"{humidity}%"

        wind = wdata.get('wind')
        try:
            if wind is None or wind == "--":
                self.wind_display = "-- m/s"
            else:
                self.wind_display = f"{float(wind):.1f} m/s"
        except Exception:
            self.wind_display = str(wind)

        pressure = wdata.get('pressure')
        try:
            if pressure is None or pressure == "--":
                self.pressure_display = "-- hPa"
            else:
                self.pressure_display = f"{int(float(pressure))} hPa"
        except Exception:
            self.pressure_display = str(pressure)

        # choose and animate weather icon (emoji) based on condition & AQI
        cond = (self.condition_display or "").lower()
        icon = "☀️"
        if "cloud" in cond:
            icon = "☁️"
        elif "rain" in cond or "drizzle" in cond:
            icon = "🌧️"
        elif "snow" in cond:
            icon = "❄️"
        elif "storm" in cond or "thunder" in cond:
            icon = "⛈️"
        elif "mist" in cond or "fog" in cond or "haze" in cond:
            icon = "🌫️"

        # if AQI is bad, overlay a small warning icon
        try:
            aqi_val_int = int(aqi_val) if aqi_val is not None else None
        except Exception:
            aqi_val_int = None

        if aqi_val_int is not None and aqi_val_int > 150:
            # unhealthy: add small mask (smoke emoji) to icon string
            icon = icon + "💨"
        self._animate_weather_icon(icon)

    # ---------------- Main background pipeline ----------------
    def update_all(self, lat_override=None, lon_override=None, city=None, region=None):
        try:
            if lat_override is None or lon_override is None:
                loc = self.determine_location()
                if not loc:
                    self._update_ui_from_data(None)
                    return
                lat, lon, city_auto, region_auto, country_auto = loc
                if city is None:
                    city = city_auto or ""
                if region is None:
                    region = region_auto or country_auto or ""
            else:
                lat, lon = lat_override, lon_override

            # weather
            try:
                wjson = fetch_weather(lat, lon, OWM_API_KEY)
                temp = wjson["main"]["temp"]
                cond = wjson["weather"][0]["description"].title()
                humidity = wjson["main"].get("humidity")
                wind = wjson.get("wind", {}).get("speed")
                pressure = wjson["main"].get("pressure")
            except Exception:
                temp = None
                cond = "Weather error"
                humidity = None
                wind = None
                pressure = None

            # IQAir AQI
            aqi_val, main_poll = (None, "")
            try:
                aqi_val, main_poll = fetch_aqi_iqair(lat, lon, IQAIR_API_KEY)
            except Exception:
                aqi_val, main_poll = (None, "")

            # OpenWeather pollutant breakdown
            pm2_5 = None
            pm10 = None
            try:
                comps = fetch_openweather_pollution(lat, lon, OWM_API_KEY)
                if comps:
                    pm2_5 = comps.get("pm2_5")
                    pm10 = comps.get("pm10")
            except Exception:
                pm2_5 = None
                pm10 = None

            data = {
                "temp": temp,
                "condition": cond,
                "city": city or "",
                "region": region or "",
                "country": "",
                "aqi": aqi_val,
                "main_pollutant": main_poll or "--",
                "pm2_5": pm2_5,
                "pm10": pm10,
                "humidity": humidity if humidity is not None else "--",
                "wind": wind if wind is not None else "--",
                "pressure": pressure if pressure is not None else "--",
            }
            self._last_fetch = data
            self._update_ui_from_data(data)
        except Exception as e:
            self._update_ui_from_data({"condition": f"Error: {e}"})

if __name__ == '__main__':
    SpaceWeatherApp().run()
