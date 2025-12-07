"""
spaceweather_iqair_centered_plus.py
Centered SpaceX/Tesla-inspired weather + AQI app with:
 - IQAir (AirVisual) for AQI (aqius)
 - OpenWeatherMap for weather + pollutant breakdown (PM2.5 / PM10)
 - Manual city search (OWM geocoding)
 - Temperature fade + scale animation on change

Requirements:
    pip install kivy plyer requests
Fill your API keys in CONFIG section below.
"""

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.animation import Animation

import threading, requests, time

# plyer GPS (optional on mobile)
try:
    from plyer import gps
    PLYER_GPS_AVAILABLE = True
except Exception:
    PLYER_GPS_AVAILABLE = False

# ----- CONFIG -----
OWM_API_KEY  = "e71fb0ca6a834cd80142f4fdcb589e3f"
IQAIR_API_KEY = "7140ea17-5768-4bc0-b63d-27350900ce4c"     # IQAir / AirVisual API key (for aqius)
UPDATE_INTERVAL = 5 * 60  # seconds

# sensible default desktop window size (won't force mobile)
Window.size = (900, 700)

KV = f'''
FloatLayout:
    id: rootfl

    BoxLayout:
        orientation: 'vertical'
        size_hint: None, 1
        width: rootfl.width if rootfl.width < {dp(420)} else {dp(420)}
        pos_hint: {{'center_x': 0.5}}
        padding: dp(12)
        spacing: dp(12)

        canvas.before:
            Color:
                rgba: (0.03, 0.035, 0.04, 1)
            Rectangle:
                pos: self.pos
                size: self.size

        # Header + search bar
        BoxLayout:
            size_hint_y: None
            height: dp(72)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: (1,1,1,0.03)
                Rectangle:
                    pos: self.pos
                    size: self.size

            BoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.6
                Label:
                    text: "SPACE WEATHER"
                    bold: True
                    font_size: '18sp'
                    color: (1,1,1,0.9)
                    halign: 'left'
                    valign: 'middle'
                Label:
                    text: "Realtime weather & AQI"
                    font_size: '10sp'
                    color: (1,1,1,0.55)
                    halign: 'left'
                    valign: 'middle'

            BoxLayout:
                size_hint_x: 0.4
                spacing: dp(6)
                TextInput:
                    id: city_input
                    hint_text: "Enter city (e.g. Delhi)"
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

        # Big card (temperature + condition)
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

            Label:
                id: temp_label
                text: app.temp_display
                font_size: '64sp'
                bold: True
                color: (1,1,1,1)
                opacity: 1.0
            Label:
                id: cond_label
                text: app.condition_display
                font_size: '18sp'
                color: (1,1,1,0.8)
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

        # AQI card + pollutants
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

            Label:
                text: 'AIR QUALITY'
                font_size: '14sp'
                color: (1,1,1,0.7)

            BoxLayout:
                spacing: dp(12)
                size_hint_y: None
                height: dp(72)

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_x: .45
                    Label:
                        text: app.aqi_display
                        font_size: '40sp'
                        bold: True
                        color: app.aqi_color
                        halign: 'left'
                        valign: 'middle'
                    Label:
                        text: app.aqi_category
                        font_size: '12sp'
                        color: (1,1,1,0.75)

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_x: .55
                    Label:
                        text: app.aqi_message
                        font_size: '13sp'
                        color: (1,1,1,0.65)
                        text_size: self.width, None
                        shorten: True
                        halign: 'left'
                        valign: 'middle'

            # Pollutant breakdown row
            GridLayout:
                cols: 3
                size_hint_y: None
                height: dp(50)
                spacing: dp(6)
                Label:
                    text: 'PM2.5'
                    font_size: '12sp'
                    color: (1,1,1,0.75)
                Label:
                    text: 'PM10'
                    font_size: '12sp'
                    color: (1,1,1,0.75)
                Label:
                    text: 'Main Pollutant'
                    font_size: '12sp'
                    color: (1,1,1,0.75)

                Label:
                    text: app.pm25_display
                    font_size: '16sp'
                    color: (1,1,1,0.95)
                    halign: 'center'
                    valign: 'middle'
                Label:
                    text: app.pm10_display
                    font_size: '16sp'
                    color: (1,1,1,0.95)
                    halign: 'center'
                    valign: 'middle'
                Label:
                    text: app.main_pollutant
                    font_size: '14sp'
                    color: (1,1,1,0.9)
                    halign: 'center'
                    valign: 'middle'


        # Details card: humidity / wind / pressure
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(140)
            padding: dp(14)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: (0.06,0.07,0.09,1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [12,]

            Label:
                text: 'DETAILS'
                font_size: '14sp'
                color: (1,1,1,0.7)
            GridLayout:
                cols: 3
                rows: 2
                row_default_height: dp(40)
                row_force_default: True
                col_default_width: self.width / 3.0
                col_force_default: False
                spacing: dp(8)

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
                    halign: 'center'
                    valign: 'middle'
                Label:
                    text: app.wind_display
                    font_size: '20sp'
                    color: (1,1,1,0.95)
                    halign: 'center'
                    valign: 'middle'
                Label:
                    text: app.pressure_display
                    font_size: '20sp'
                    color: (1,1,1,0.95)
                    halign: 'center'
                    valign: 'middle'

        Widget:
            size_hint_y: None
            height: dp(10)
'''

# ----- Helper functions -----
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
    """Use OpenWeatherMap direct geocoding to convert city name to (lat, lon, name, region, country)"""
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
    """
    OpenWeatherMap Air Pollution API returns components including pm2_5 and pm10.
    Endpoint: /data/2.5/air_pollution?lat={lat}&lon={lon}&appid={key}
    """
    try:
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
        # j["list"][0]["components"] contains pm2_5, pm10 etc
        if "list" in j and j["list"]:
            comps = j["list"][0].get("components", {})
            return comps  # dict with pm2_5, pm10, no2, so2, co, o3
    except Exception:
        pass
    return None

def fetch_aqi_iqair(lat, lon, key):
    """IQAir nearest_city for aqius and main pollutant if present."""
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

# ----- App -----
class SpaceWeatherApp(App):
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

    # internal
    _last_fetch = None
    _last_temp_value = None

    def build(self):
        self.title = "SpaceWeather (Centered + AQ)"
        return Builder.load_string(KV)

    def on_start(self):
        # initial background fetch
        Clock.schedule_once(lambda dt: threading.Thread(target=self.update_all, daemon=True).start())
        # periodic updates
        Clock.schedule_interval(lambda dt: threading.Thread(target=self.update_all, daemon=True).start(), UPDATE_INTERVAL)

    def manual_refresh(self):
        threading.Thread(target=self.update_all, daemon=True).start()

    def search_city(self, city_text):
        """Triggered by search box — resolve city to lat/lon and fetch"""
        if not city_text or not city_text.strip():
            return
        threading.Thread(target=self._search_and_fetch, args=(city_text.strip(),), daemon=True).start()

    def _search_and_fetch(self, city_text):
        res = owm_geocode_city(city_text, OWM_API_KEY)
        if not res:
            # show not found in UI
            self._update_ui_from_data({"condition": "City not found"})
            return
        lat, lon, name, state, country = res
        # call the common fetch pipeline with given lat/lon and forced location name
        self.update_all(lat_override=lat, lon_override=lon, city=name, region=state or country)

    def determine_location(self):
        """Try device GPS via plyer, otherwise IP geolocation"""
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

    from kivy.metrics import dp
    @mainthread
    def _animate_temp_change(self, label_widget, new_text):
        """Fade + scale animation on temperature label when it changes."""
        try:
            # Start small and transparent (must use numeric values)
            label_widget.opacity = 0.0
            label_widget.font_size = dp(44)
            label_widget.text = new_text

            # Animate to final size (numeric dp value)
            anim = Animation(opacity=1.0, font_size=dp(64), d=0.45, t='out_cubic')
            anim.start(label_widget)
        except Exception:
            # fallback if animation fails
            label_widget.text = new_text
            label_widget.opacity = 1.0
            label_widget.font_size = dp(64)


    @mainthread
    def _update_ui_from_data(self, wdata):
        """Update UI on main thread"""
        if not wdata:
            self.condition_display = "Unable to fetch data"
            return

        # Temperature — trigger animation if value changed
        temp = wdata.get('temp')
        if temp is None:
            new_temp_text = "--°C"
        else:
            try:
                new_temp_text = f"{float(temp):.0f}°C"
            except Exception:
                new_temp_text = f"{temp}°C"

        # Animate only if different
        if new_temp_text != self.temp_display:
            # find label widget by id and animate
            try:
                temp_label = self.root.ids.temp_label
                self._animate_temp_change(temp_label, new_temp_text)
            except Exception:
                self.temp_display = new_temp_text
        else:
            self.temp_display = new_temp_text

        self.condition_display = wdata.get("condition", "—")
        city = wdata.get('city','')
        region = wdata.get('region','')
        self.location_display = f"{city} {region}".strip()
        self.updated_display = f"Updated {time.strftime('%H:%M:%S')}"

        # AQI via IQAir
        aqi_val = wdata.get("aqi")
        if aqi_val is not None:
            self.aqi_display = str(aqi_val)
            cat, msg, color = aqi_category_and_color(aqi_val)
            self.aqi_category = cat
            self.aqi_message = msg
            self.aqi_color = color
        else:
            self.aqi_display = "--"
            self.aqi_category = "No AQI"
            self.aqi_message = "Data unavailable"
            self.aqi_color = [1,1,1,1]

        # Pollutants
        pm25 = wdata.get("pm2_5")
        pm10 = wdata.get("pm10")
        if pm25 is None:
            self.pm25_display = "-- µg/m³"
        else:
            try:
                self.pm25_display = f"{float(pm25):.1f} µg/m³"
            except Exception:
                self.pm25_display = str(pm25)

        if pm10 is None:
            self.pm10_display = "-- µg/m³"
        else:
            try:
                self.pm10_display = f"{float(pm10):.1f} µg/m³"
            except Exception:
                self.pm10_display = str(pm10)

        main_poll = wdata.get("main_pollutant") or "--"
        self.main_pollutant = main_poll

        # Details: humidity/wind/pressure formatting
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

    def update_all(self, lat_override=None, lon_override=None, city=None, region=None):
        """
        Main background pipeline. If lat_override/lon_override provided (via search),
        use them; otherwise auto-detect location.
        """
        try:
            if lat_override is None or lon_override is None:
                loc = self.determine_location()
                if not loc:
                    self._update_ui_from_data(None)
                    return
                lat, lon, city_auto, region_auto, country_auto = loc
                # prefer city override if provided
                if city is None:
                    city = city_auto or ""
                if region is None:
                    region = region_auto or country_auto or ""
            else:
                lat, lon = lat_override, lon_override

            # fetch weather
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

            # OpenWeather pollutant breakdown for PM2.5 / PM10
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
