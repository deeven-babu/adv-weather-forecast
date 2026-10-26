"""Centralized translation resources for multilingual UI and generated messages."""

import logging
import re

_logger = logging.getLogger(__name__)
_logged_missing = set()

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en": "English", "te": "తెలుగు", "hi": "हिन्दी"}
LANGUAGE_ALIASES = {
    "english": "en",
    "en": "en",
    "telugu": "te",
    "te": "te",
    "hi": "hi",
    "hindi": "hi",
    "default": "en",
}

UI_TEXT = {
    "en": {
        "nav.dashboard": "Dashboard",
        "nav.assistant": "AI Assistant",
        "nav.profile": "Profile",
        "nav.login": "Log in",
        "nav.logout": "Log out",
        "nav.register": "Register",
        "nav.home": "Home",
        "nav.how_it_works": "How it works",
        "nav.language": "Language",
        "theme.toggle": "Toggle color theme",
        "search.weather": "Search weather",
        "search.loading": "Loading...",
        "weather.live": "Live data",
        "weather.ai": "Weather AI",
        "weather.ai_summary": "AI-Powered Summary",
        "weather.today": "Today's Weather",
        "weather.alerts": "Weather Alerts",
        "weather.recommendations": "Recommendation",
        "weather.mode_for": "For your",
        "weather.current_conditions": "Current conditions",
        "weather.humidity": "Humidity",
        "weather.wind": "Wind",
        "weather.precipitation": "Precipitation",
        "weather.pressure": "Pressure",
        "weather.rain_chance": "Rain chance",
        "weather.risk_outlook": "Risk outlook",
        "weather.forecast": "Forecast",
        "weather.next_seven_days": "Next seven days",
        "weather.live_data": "Live data from Open-Meteo",
        "weather.updated": "Updated when you search",
        "weather.ask_ai": "Ask AI assistant",
        "weather.conditions": "Read the conditions.",
        "weather.select_mode": "Select a mode",
        "weather.how_use": "How will you use this weather?",
        "weather.search_placeholder": "Search city or town",
        "weather.search_label": "Search for a city or town",
        "weather.disclaimer": "Answers use the selected location's live weather response and available model estimate. They are not official warnings.",
        "mode.general": "General",
        "mode.farmer": "Farmer",
        "mode.travel": "Travel",
        "mode.daily_commute": "Commute",
        "mode.outdoor_activity": "Outdoor",
        "mode_context.general": "For planning,",
        "mode_context.farmer": "For farm planning,",
        "mode_context.travel": "For travel planning,",
        "mode_context.daily_commute": "For commute planning,",
        "mode_context.outdoor_activity": "For outdoor activity planning,",
        "button.ask": "Ask",
        "button.search": "Search",
        "button.clear": "Clear chat",
        "button.back": "Back to dashboard",
        "button.submit": "Submit",
        "form.question_placeholder": "Ask about",
        "chat.loading": "Checking the latest available weather...",
        "chat.empty": "Ask a weather question to continue.",
        "chat.missing_location": "Select a location before asking a question.",
        "chat.default": "I can answer about current conditions, the seven-day forecast, rain probability, or the available disaster-risk indicators.",
        "error.invalid_mode": "Invalid mode. Valid modes are:",
        "error.select_location": "Select a location first.",
        "error.login_required": "Please log in.",
        "error.weather_unavailable": "The weather service is temporarily unavailable.",
        "alert.title": "Weather Alerts",
        "alert.severity.low": "Low",
        "alert.severity.moderate": "Moderate",
        "alert.severity.high": "High",
        "alert.heavy_rain": "Heavy Rain",
        "alert.high_temperature": "High Temperature",
        "alert.strong_wind": "Strong Wind",
        "alert.rain_probability": "High Rain Probability",
        "alert.poor_outdoor": "Poor Outdoor Conditions",
        "alert.travel_caution": "Travel Caution",
        "alert.default": "Weather alert",
        "recommendation.default": "Weather conditions appear suitable for outdoor activities.",
        "risk.flood": "Flood Risk",
        "risk.heatwave": "Heatwave Risk",
        "risk.rain": "Heavy Rain Risk",
        "forecast.rain": "Rain",
        "forecast.temperature": "Temperature",
        "label.temperature": "Temperature",
        "label.humidity": "Humidity",
        "label.wind": "Wind",
        "label.rain_probability": "Rain probability",
        "label.precipitation": "Precipitation",
        "label.forecast": "Forecast",
        "label.conditions": "Conditions",
        "label.risk": "Risk",
        "label.alerts": "Alerts",
        "label.recommendation": "Recommendation",
    },
    "te": {
        "nav.dashboard": "డాష్‌బోర్డ్",
        "nav.assistant": "ఎఐ సహాయకుడు",
        "nav.profile": "ప్రొఫైల్",
        "nav.login": "లాగిన్",
        "nav.logout": "లాగ్అవుట్",
        "nav.register": "నమోదు",
        "nav.home": "హోమ్",
        "nav.how_it_works": "ఇది ఎలా పని చేస్తుంది",
        "nav.language": "భాష",
        "theme.toggle": "రంగు థీమ్ మార్చు",
        "search.weather": "వాతావరణం వెతుకు",
        "search.loading": "లోడ్ అవుతోంది...",
        "weather.live": "లైవ్ డేటా",
        "weather.ai": "వాతావరణ ఎఐ",
        "weather.ai_summary": "ఎఐ సారాంశం",
        "weather.today": "నేటి వాతావరణం",
        "weather.alerts": "వాతావరణ హెచ్చరికలు",
        "weather.recommendations": "సిఫార్సు",
        "weather.mode_for": "మీ కోసం",
        "weather.current_conditions": "ప్రస్తుత పరిస్థితులు",
        "weather.humidity": "తేమ",
        "weather.wind": "గాలి",
        "weather.precipitation": "వర్షపాతం",
        "weather.pressure": "పీడనం",
        "weather.rain_chance": "వర్షపు అవకాశం",
        "weather.risk_outlook": "జాగ్రత్త సూచన",
        "weather.forecast": "వాతావరణ అంచనా",
        "weather.next_seven_days": "తదుపరి 7 రోజులు",
        "weather.live_data": "Open-Meteo నుండి లైవ్ డేటా",
        "weather.updated": "శోధించినప్పుడు తాజాకరించబడుతుంది",
        "weather.ask_ai": "ఎఐ సహాయకుడిని అడగండి",
        "weather.conditions": "పరిస్థితులను చదవండి.",
        "weather.select_mode": "మోడ్ ఎంచుకోండి",
        "weather.how_use": "మీరు వాతావరణాన్ని ఎలా ఉపయోగించాలనుకుంటున్నారు?",
        "weather.search_placeholder": "నగరం/గ్రామం వెతుకు",
        "weather.search_label": "నగరం లేదా గ్రామం కోసం వెతుకు",
        "weather.disclaimer": "సమాధానాలు ఎంపిక చేసిన స్థలంపై ఉన్న లైవ్ వాతావరణం మరియు అందుబాటులో ఉన్న మోడల్ అంచనాలపై ఆధారపడి ఉంటాయి. ఇవి అధికారిక హెచ్చరికలు కావు.",
        "mode.general": "సాధారణ",
        "mode.farmer": "రైతు",
        "mode.travel": "ప్రయాణం",
        "mode.daily_commute": "కామ్యూట్",
        "mode.outdoor_activity": "అవుట్‌డోర్",
        "mode_context.general": "ప్లానింగ్ కోసం,",
        "mode_context.farmer": "వ్యవసాయ ప్రణాళిక కోసం,",
        "mode_context.travel": "ప్రయాణ ప్రణాళిక కోసం,",
        "mode_context.daily_commute": "కామ్యూట్ ప్రణాళిక కోసం,",
        "mode_context.outdoor_activity": "అవుట్‌డోర్ కార్యకలాపాల ప్రణాళిక కోసం,",
        "button.ask": "అడుగు",
        "button.search": "వెతుకు",
        "button.clear": "చాట్ క్లియర్ చేయి",
        "button.back": "డాష్‌బోర్డ్‌కు తిరిగి",
        "button.submit": "సమర్పించు",
        "form.question_placeholder": "దీనిని అడుగు",
        "chat.loading": "చివరి వాతావరణ సమాచారం తనిఖీ చేయబడుతోంది...",
        "chat.empty": "వాతావరణ ప్రశ్న అడగండి.",
        "chat.missing_location": "ప్రశ్న అడగడానికి స్థలాన్ని ఎంచుకోండి.",
        "chat.default": "ప్రస్తుత పరిస్థితులు, 7-రోజుల సూచన, వర్షం అవకాశాలు లేదా అందుబాటులో ఉన్న అపాయం సూచనలు గురించి నేను వివరించగలను.",
        "error.invalid_mode": "చెల్లని మోడ్. చెల్లుబాటు మోడ్లు:",
        "error.select_location": "స్థలాన్ని ఎంచుకోండి.",
        "error.login_required": "దయచేసి లాగిన్ చేయండి.",
        "error.weather_unavailable": "వాతావరణ సేవ తాత్కాలికంగా అందుబాటులో లేదు.",
        "alert.title": "వాతావరణ హెచ్చరికలు",
        "alert.severity.low": "తక్కువ",
        "alert.severity.moderate": "మితమైన",
        "alert.severity.high": "అధిక",
        "alert.heavy_rain": "భారీ వర్షం",
        "alert.high_temperature": "అధిక ఉష్ణోగ్రత",
        "alert.strong_wind": "బలమైన గాలి",
        "alert.rain_probability": "అధిక వర్షపు అవకాశం",
        "alert.poor_outdoor": "అవుట్‌డోర్ పరిస్థితులు అనుకూలం కావు",
        "alert.travel_caution": "ప్రయాణ జాగ్రత్త",
        "alert.default": "వాతావరణ హెచ్చరిక",
        "recommendation.default": "వాతావరణ పరిస్థితులు అవుట్‌డోర్ కార్యకలాపాలకు సరిపోతున్నాయి.",
        "risk.flood": "వరద ప్రమాదం",
        "risk.heatwave": "ఉష్ణం ప్రమాదం",
        "risk.rain": "భారీ వర్ష ప్రమాదం",
        "forecast.rain": "వర్షం",
        "forecast.temperature": "ఉష్ణోగ్రత",
        "label.temperature": "ఉష్ణోగ్రత",
        "label.humidity": "తేమ",
        "label.wind": "గాలి",
        "label.rain_probability": "వర్షం అవకాశము",
        "label.precipitation": "వర్షపాతం",
        "label.forecast": "వాతావరణ అంచనా",
        "label.conditions": "పరిస్థితులు",
        "label.risk": "ప్రమాదం",
        "label.alerts": "హెచ్చరికలు",
        "label.recommendation": "సిఫార్సు",
    },
    "hi": {
        "nav.dashboard": "डैशबोर्ड",
        "nav.assistant": "एआई सहायक",
        "nav.profile": "प्रोफाइल",
        "nav.login": "लॉग इन",
        "nav.logout": "लॉग आउट",
        "nav.register": "पंजीकरण",
        "nav.home": "होम",
        "nav.how_it_works": "यह कैसे काम करता है",
        "nav.language": "भाषा",
        "theme.toggle": "रंग थीम बदलें",
        "search.weather": "मौसम खोजें",
        "search.loading": "लोड हो रहा है...",
        "weather.live": "लाइव डेटा",
        "weather.ai": "मौसम एआई",
        "weather.ai_summary": "एआई सारांश",
        "weather.today": "आज का मौसम",
        "weather.alerts": "मौसम अलर्ट",
        "weather.recommendations": "सिफारिश",
        "weather.mode_for": "आपके लिए",
        "weather.current_conditions": "वर्तमान परिस्थितियाँ",
        "weather.humidity": "नमी",
        "weather.wind": "हवा",
        "weather.precipitation": "वर्षा",
        "weather.pressure": "दबाव",
        "weather.rain_chance": "बारिश की संभावना",
        "weather.risk_outlook": "जोखिम पूर्वानुमान",
        "weather.forecast": "मौसम पूर्वानुमान",
        "weather.next_seven_days": "अगले 7 दिन",
        "weather.live_data": "Open-Meteo से लाइव डेटा",
        "weather.updated": "खोजते समय अपडेट होता है",
        "weather.ask_ai": "एआई सहायक से पूछें",
        "weather.conditions": "परिस्थितियाँ देखें.",
        "weather.select_mode": "मोड चुनें",
        "weather.how_use": "आप मौसम का उपयोग कैसे करेंगे?",
        "weather.search_placeholder": "शहर या गाँव खोजें",
        "weather.search_label": "शहर या गाँव खोजें",
        "weather.disclaimer": "उत्तर चुने गए स्थान के लाइव मौसम डेटा और उपलब्ध मॉडल अनुमान पर आधारित हैं। वे आधिकारिक चेतावनी नहीं हैं।",
        "mode.general": "सामान्य",
        "mode.farmer": "किसान",
        "mode.travel": "यात्रा",
        "mode.daily_commute": "यात्रा",
        "mode.outdoor_activity": "आउटडोर",
        "mode_context.general": "योजना के लिए,",
        "mode_context.farmer": "कृषि योजना के लिए,",
        "mode_context.travel": "यात्रा योजना के लिए,",
        "mode_context.daily_commute": "यात्रा योजना के लिए,",
        "mode_context.outdoor_activity": "आउटडोर गतिविधि योजना के लिए,",
        "button.ask": "पूछें",
        "button.search": "खोजें",
        "button.clear": "चैट साफ़ करें",
        "button.back": "डैशबोर्ड पर लौटें",
        "button.submit": "सबमिट",
        "form.question_placeholder": "यह पूछें",
        "chat.loading": "नवीनतम मौसम की जाँच की जा रही है...",
        "chat.empty": "मौसम का सवाल पूछें।",
        "chat.missing_location": "प्रश्न पूछने के लिए स्थान चुनें।",
        "chat.default": "मैं वर्तमान स्थिति, 7-दिवसीय पूर्वानुमान, बारिश की संभावना या उपलब्ध आपदा-जोखिम संकेतों के बारे में उत्तर दे सकता हूँ।",
        "error.invalid_mode": "अमान्य मोड। मान्य मोड हैं:",
        "error.select_location": "स्थान चुनें।",
        "error.login_required": "कृपया लॉग इन करें।",
        "error.weather_unavailable": "मौसम सेवा अस्थायी रूप से उपलब्ध नहीं है।",
        "alert.title": "मौसम अलर्ट",
        "alert.severity.low": "कम",
        "alert.severity.moderate": "मध्यम",
        "alert.severity.high": "उच्च",
        "alert.heavy_rain": "तेज़ बारिश",
        "alert.high_temperature": "अधिक तापमान",
        "alert.strong_wind": "तेज़ हवा",
        "alert.rain_probability": "उच्च बारिश संभावना",
        "alert.poor_outdoor": "अच्छा नहीं आउटडोर स्थिति",
        "alert.travel_caution": "यात्रा सावधानी",
        "alert.default": "मौसम अलर्ट",
        "recommendation.default": "मौसम की स्थिति आउटडोर गतिविधियों के लिए उपयुक्त है।",
        "risk.flood": "बाढ़ जोखिम",
        "risk.heatwave": "हीटवेव जोखिम",
        "risk.rain": "तेज़ बारिश जोखिम",
        "forecast.rain": "बारिश",
        "forecast.temperature": "तापमान",
        "label.temperature": "तापमान",
        "label.humidity": "नमी",
        "label.wind": "हवा",
        "label.rain_probability": "बारिश की संभावना",
        "label.precipitation": "वर्षा",
        "label.forecast": "पूर्वानुमान",
        "label.conditions": "परिस्थितियाँ",
        "label.risk": "जोखिम",
        "label.alerts": "अलर्ट",
        "label.recommendation": "सिफारिश",
    },
}

ALERT_TYPE_TRANSLATIONS = {
    "Heavy Rain": {"te": "భారీ వర్షం", "hi": "तेज़ बारिश"},
    "High Temperature": {"te": "అధిక ఉష్ణోగ్రత", "hi": "अधिक तापमान"},
    "Strong Wind": {"te": "బలమైన గాలి", "hi": "तेज़ हवा"},
    "Moderate Wind": {"te": "మితమైన గాలి", "hi": "मध्यम हवा"},
    "Moderate Rain": {"te": "మితమైన వర్షం", "hi": "मध्यम बारिश"},
    "High Rain Probability": {"te": "అధిక వర్షం అవకాశం", "hi": "उच्च बारिश संभावना"},
    "Poor Outdoor Conditions": {"te": "చెడు అవుట్‌డోర్ పరిస్థితులు", "hi": "अच्छी नहीं आउटडोर स्थिति"},
    "Travel Caution": {"te": "ప్రయాణ జాగ్రత్త", "hi": "यात्रा सावधानी"},
    "Warm Temperature": {"te": "వెచ్చని ఉష్ణోగ్రత", "hi": "गर्म तापमान"},
    "Thunderstorm": {"te": "తుఫాను", "hi": "तूफ़ान"},
}

SEVERITY_TRANSLATIONS = {
    "Low": {"te": "తక్కువ", "hi": "कम"},
    "Moderate": {"te": "మితమైన", "hi": "मध्यम"},
    "High": {"te": "అధిక", "hi": "उच्च"},
}

WEATHER_CONDITION_TRANSLATIONS = {
    "clear sky": {"te": "స్పష్టమైన ఆకాశం", "hi": "साफ़ आकाश"},
    "mainly clear": {"te": "ప్రధానంగా స్పష్టంగా", "hi": "मुख्यतः साफ़"},
    "overcast": {"te": "మేఘావృతం", "hi": "बादलों से घिरा"},
    "light rain": {"te": "తేలికపాటి వర్షం", "hi": "हल्की बारिश"},
    "heavy rain": {"te": "భారీ వర్షం", "hi": "तेज़ बारिश"},
    "rain showers": {"te": "వర్షపు జల్లులు", "hi": "बारिश की बौछारें"},
    "partly cloudy": {"te": "పాక్షిక మేఘావృతం", "hi": "आंशिक बादल"},
    "cloudy": {"te": "మేఘావృతం", "hi": "बादलयुक्त"},
    "clear": {"te": "స్పష్టమైన వాతావరణం", "hi": "साफ मौसम"},
    "sunny": {"te": "సూర్యకాంతి", "hi": "धूप"},
    "rainy": {"te": "వర్షం ఉన్న", "hi": "बारिश वाला"},
    "drizzle": {"te": "చిన్ని వర్షం", "hi": "हल्की बारिश"},
    "storm": {"te": "తుఫాను", "hi": "तूफ़ान"},
    "thunderstorm": {"te": "మెరుపులతో కూడిన తుఫాను", "hi": "तूफ़ान"},
    "windy": {"te": "గాలివేళ్ళు", "hi": "हवा वाला"},
    "humid": {"te": "తేమగా", "hi": "आर्द्र"},
    "mixed conditions": {"te": "మిశ్రమ పరిస్థితులు", "hi": "मिश्रित परिस्थितियाँ"},
    "pleasant": {"te": "మంచు వాతావరణం", "hi": "सुखद"},
    "warm": {"te": "వెచ్చని", "hi": "गर्म"},
    "cool": {"te": "చల్లని", "hi": "ठंडा"},
    "high likelihood of rain": {"te": "వర్షం ఉండే అధిక సంభావ్యత", "hi": "बारिश की अधिक संभावना"},
    "possible rain": {"te": "వర్షం వచ్చే అవకాశం", "hi": "बारिश की संभावना"},
    "low chance of rain": {"te": "వర్షం తక్కువ అవకాశం", "hi": "बारिश की कम संभावना"},
}

COMMON_TRANSLATIONS = {
    "Today in": {"te": "నేడు", "hi": "आज"},
    "with": {"te": "తో", "hi": "के साथ"},
    "humid": {"te": "తేమ", "hi": "नमी"},
    "wind": {"te": "గాలి", "hi": "हवा"},
    "wind speed": {"te": "గాలి వేగం", "hi": "हवा की गति"},
    "rain": {"te": "వర్షం", "hi": "बारिश"},
    "chance": {"te": "అవకాశం", "hi": "संभावना"},
    "outdoor": {"te": "అవుట్‌డోర్", "hi": "आउटडोर"},
    "conditions": {"te": "పరిస్థితులు", "hi": "परिस्थितियाँ"},
    "tomorrow": {"te": "రేపు", "hi": "कल"},
    "today": {"te": "నేడు", "hi": "आज"},
    "temperature": {"te": "ఉష్ణోగ్రత", "hi": "तापमान"},
    "cloud cover": {"te": "మేఘాల కవచం", "hi": "बादल आवरण"},
    "carry an umbrella": {"te": "గొడుగు తీసుకెళ్లండి", "hi": "छाता साथ रखें"},
    "umbrella": {"te": "గొడుగు", "hi": "छाता"},
    "recommendation": {"te": "సిఫార్సు", "hi": "सिफारिश"},
    "alert": {"te": "హెచ్చరిక", "hi": "अलर्ट"},
    "warning": {"te": "హెచ్చరిక", "hi": "चेतावनी"},
    "risk": {"te": "జాగ్రత్త", "hi": "जोखिम"},
    "weather": {"te": "వాతావరణం", "hi": "मौसम"},
    "general": {"te": "సాధారణ", "hi": "सामान्य"},
    "humidity": {"te": "తేమ", "hi": "नमी"},
    "pressure": {"te": "పీడనం", "hi": "दबाव"},
    "precipitation": {"te": "వర్షపాతం", "hi": "वर्षा"},
    "visibility": {"te": "దృశ్యమానత", "hi": "दृश्यता"},
    "direction": {"te": "దిశ", "hi": "दिशा"},
    "sunrise": {"te": "సూర్యోదయం", "hi": "सूर्योदय"},
    "sunset": {"te": "సూర్యాస్తమయం", "hi": "सूर्यास्त"},
    "feels like": {"te": "అనుభూతి", "hi": "महसूस"},
    "live": {"te": "లైవ్", "hi": "लाइव"},
    "good": {"te": "మంచిది", "hi": "अच्छा"},
    "rain chance": {"te": "వర్షం అవకాశం", "hi": "बारिश की संभावना"},
    "risk level": {"te": "ప్రమాద స్థాయి", "hi": "जोखिम स्तर"},
    "machine learning estimate": {"te": "మెషిన్ లెర్నింగ్ అంచనా", "hi": "मशीन लर्निंग अनुमान"},
    "AI Rainfall Prediction": {"te": "ఎఐ వర్షపాత అంచనా", "hi": "एआई वर्षा पूर्वानुमान"},
    "Top model factors": {"te": "మోడల్ ప్రధాన కారకాలు", "hi": "मॉडल के प्रमुख कारक"},
    "Next seven days": {"te": "తదుపరి ఏడు రోజులు", "hi": "अगले सात दिन"},
    "Forecast.": {"te": "వాతావరణ అంచనా.", "hi": "पूर्वानुमान।"},
    "Disaster risk": {"te": "విపత్తు ప్రమాదం", "hi": "आपदा जोखिम"},
    "Risk outlook.": {"te": "ప్రమాద సూచన.", "hi": "जोखिम पूर्वानुमान।"},
    "Location intelligence": {"te": "స్థల సమాచారం", "hi": "स्थान जानकारी"},
    "Map.": {"te": "మ్యాప్.", "hi": "मानचित्र।"},
    "Use my location": {"te": "నా స్థలాన్ని ఉపయోగించండి", "hi": "मेरा स्थान उपयोग करें"},
    "Weather unavailable": {"te": "వాతావరణం అందుబాటులో లేదు", "hi": "मौसम उपलब्ध नहीं है"},
    "Good": {"te": "మంచిది", "hi": "अच्छा"},
}

MODE_NAME_TRANSLATIONS = {
    "general": {"te": "సాధారణ", "hi": "सामान्य"},
    "farmer": {"te": "రైతు", "hi": "किसान"},
    "travel": {"te": "ప్రయాణం", "hi": "यात्रा"},
    "daily_commute": {"te": "కామ్యూట్", "hi": "यात्रा"},
    "outdoor_activity": {"te": "అవుట్‌డోర్", "hi": "आउटडोर"},
}

RECOMMENDATION_PHRASES = {
    "Heavy rainfall is possible. Plan extra travel time and carry rain protection.": {"te": "భారీ వర్షం వచ్చే అవకాశం ఉంది. అదనపు ప్రయాణ సమయాన్ని కేటాయించి వర్షరక్షణ తీసుకెళ్లండి.", "hi": "भारी बारिश की संभावना है। अतिरिक्त यात्रा समय रखें और बारिश से बचाव सामग्री साथ रखें।"},
    "High chance of rain. Outdoor activities may be unfavorable.": {"te": "వర్షం పడే అవకాశం ఎక్కువగా ఉంది. బయట కార్యకలాపాలు అనుకూలంగా ఉండకపోవచ్చు.", "hi": "बारिश होने की अधिक संभावना है। बाहरी गतिविधियाँ अनुकूल नहीं हो सकती हैं।"},
    "Detailed hourly forecast is not available. Check the 7-day forecast for better planning.": {"te": "గంటల వారీ వాతావరణ అంచనా అందుబాటులో లేదు. మెరుగైన ప్రణాళిక కోసం 7 రోజుల అంచనాను చూడండి.", "hi": "घंटेवार पूर्वानुमान उपलब्ध नहीं है। बेहतर योजना के लिए 7-दिन का पूर्वानुमान देखें।"},
    "The available weather and model inputs are used to estimate rainfall for {0}; feature importance details are not available for this prediction.": {"te": "{0} కోసం వర్షపాతాన్ని అంచనా వేయడానికి అందుబాటులో ఉన్న వాతావరణం మరియు మోడల్ ఇన్‌పుట్‌లను ఉపయోగిస్తారు; ఈ అంచనాకు ఫీచర్ ప్రాముఖ్యత వివరాలు అందుబాటులో లేవు.", "hi": "{0} के लिए बारिश का अनुमान लगाने हेतु उपलब्ध मौसम और मॉडल इनपुट का उपयोग किया जाता है; इस अनुमान के लिए फीचर महत्व विवरण उपलब्ध नहीं हैं।"},
    "The ML rainfall estimate for {0} is based on the supplied weather inputs. The model's leading available factors are {1}.": {"te": "{0} కోసం ఎంఎల్ వర్షపాతం అంచనా అందించిన వాతావరణ ఇన్‌పుట్‌లపై ఆధారపడి ఉంటుంది. మోడల్‌లో అందుబాటులో ఉన్న ప్రధాన కారకాలు {1}.", "hi": "{0} के लिए एमएल बारिश का अनुमान दिए गए मौसम इनपुट पर आधारित है। मॉडल के प्रमुख उपलब्ध कारक हैं: {1}."},
    "Consider carrying an umbrella or rain protection.": {"te": "గొడుగు లేదా వర్షరక్షణ తీసుకెళ్లండి.", "hi": "छाता या बारिश से बचाव सामग्री साथ रखें।"},
    "Use appropriate sun protection and stay hydrated.": {"te": "సరైన సూర్యరక్షణ ఉపయోగించండి మరియు నీరు తాగండి.", "hi": "उचित सूर्य सुरक्षा का उपयोग करें और हाइड्रेटेड रहें।"},
    "Use sun protection if spending time outdoors.": {"te": "బయట సమయం గడిపేటప్పుడు సూర్యరక్షణ ఉపయోగించండి.", "hi": "अगर आप बाहर समय बिताते हैं तो सूर्य सुरक्षा का उपयोग करें。"},
    "Strong winds are expected. Secure loose items outdoors.": {"te": "బలమైన గాలి వచ్చే అవకాశం ఉంది. బయటి సుత్తి వస్తువులను భద్రపరచండి.", "hi": "तेज़ हवा आने की संभावना है। बाहर की हल्की वस्तुओं को सुरक्षित करें।"},
    "Weather conditions appear suitable for outdoor activities.": {"te": "వాతావరణ పరిస్థితులు అవుట్‌డోర్ కార్యకలాపాలకు సరిపోతున్నాయి.", "hi": "मौसम की स्थिति आउटडोर गतिविधियों के लिए उपयुक्त है।"},
    "Heavy rainfall": {"te": "భారీ వర్షపాతం", "hi": "तेज़ बारिश"},
    "Rainfall": {"te": "వర్షపాతం", "hi": "बारिश"},
    "Monitor crop conditions.": {"te": "పంట పరిస్థితులను పర్యవేక్షించండి.", "hi": "फसल की स्थिति की निगरानी करें।"},
    "Consider irrigation planning.": {"te": "నీటి వాడకం ప్రణాళిక చేయండి.", "hi": "सिंचाई की योजना बनाएं।"},
    "Plan extra travel time and carry rain protection.": {"te": "అదనపు ప్రయాణ సమయం ప్లాన్ చేసుకోండి మరియు వర్ష రక్షణ తీసుకెళ్లండి.", "hi": "अतिरिक्त यात्रा समय तय करें और बारिश से बचाव सामग्री साथ रखें।"},
    "Carry rain protection.": {"te": "వర్షరక్షణ తీసుకెళ్లండి.", "hi": "बारिश से बचाव सामग्री साथ रखें।"},
    "Allow extra time for commute.": {"te": "కామ్యూట్‌కి అదనపు సమయం వదిలివేయండి.", "hi": "यात्रा के लिए अतिरिक्त समय रखें।"},
    "Rain is possible. Carry rain protection if you are going outside.": {"te": "వర్షం వచ్చే అవకాశం ఉంది. బయటకు వెళ్తే వర్షరక్షణ తీసుకెళ్లండి.", "hi": "बारिश की संभावना है। बाहर जाते समय बारिश से बचाव सामग्री साथ रखें।"},
    "Rainfall is possible. Consider carrying rain protection.": {"te": "వర్షం వచ్చే అవకాశం ఉంది. వర్షరక్షణ తీసుకెళ్లడాన్ని పరిశీలించండి.", "hi": "बारिश की संभावना है। बारिश से बचाव सामग्री साथ रखने पर विचार करें।"},
    "High chance of rainfall is expected. Carry rain protection.": {"te": "వర్షం పడే అవకాశం ఎక్కువగా ఉంది. వర్షరక్షణ తీసుకెళ్లండి.", "hi": "बारिश होने की अधिक संभावना है। बारिश से बचाव सामग्री साथ रखें।"},
    "Weather conditions may not be favorable for outdoor activities.": {"te": "వాతావరణ పరిస్థితులు బయట కార్యకలాపాలకు అనుకూలంగా ఉండకపోవచ్చు.", "hi": "मौसम की स्थिति बाहरी गतिविधियों के लिए अनुकूल नहीं हो सकती है।"},
    "Rain and wind are expected. Exercise extra caution during travel.": {"te": "వర్షం మరియు గాలి వచ్చే అవకాశం ఉంది. ప్రయాణంలో అదనపు జాగ్రత్త వహించండి.", "hi": "बारिश और हवा आने की संभावना है। यात्रा के दौरान अतिरिक्त सावधानी बरतें।"},
    "Warm temperatures are expected. Use sun protection if going outside.": {"te": "వెచ్చని ఉష్ణోగ్రతలు ఉండే అవకాశం ఉంది. బయటకు వెళ్తే సూర్యరక్షణ ఉపయోగించండి.", "hi": "गर्म तापमान रहने की संभावना है। बाहर जाते समय सूर्य सुरक्षा का उपयोग करें।"},
    "Moderate winds are expected. Be cautious if traveling.": {"te": "మితమైన గాలులు వీస్తాయి. ప్రయాణిస్తే జాగ్రత్తగా ఉండండి.", "hi": "मध्यम हवा चलने की संभावना है। यात्रा करते समय सावधान रहें।"},
    "Thunderstorms are possible. Avoid outdoor activities and secure loose objects.": {"te": "తుఫానులు వచ్చే అవకాశం ఉంది. బయట కార్యకలాపాలను నివారించి, వదులుగా ఉన్న వస్తువులను భద్రపరచండి.", "hi": "तूफ़ान आने की संभावना है। बाहरी गतिविधियों से बचें और ढीली वस्तुओं को सुरक्षित करें।"},
    "Rainfall ({0}% probability) is expected. Monitor crop conditions.": {"te": "వర్షపాతం ({0}% అవకాశం) ఉండవచ్చు. పంట పరిస్థితులను పర్యవేక్షించండి.", "hi": "बारिश ({0}% संभावना) होने की संभावना है। फसल की स्थिति पर नज़र रखें।"},
    "No significant rainfall expected. Consider irrigation planning.": {"te": "గణనీయమైన వర్షపాతం ఉండదు. నీటిపారుదల ప్రణాళికను పరిశీలించండి.", "hi": "महत्वपूर्ण बारिश की संभावना नहीं है। सिंचाई की योजना बनाने पर विचार करें।"},
    "Adequate precipitation detected. Check irrigation needs.": {"te": "తగినంత వర్షపాతం నమోదైంది. నీటిపారుదల అవసరాలను పరిశీలించండి.", "hi": "पर्याप्त वर्षा दर्ज हुई है। सिंचाई की ज़रूरत जाँचें।"},
    "Weather conditions may be favorable for field activities.": {"te": "వాతావరణ పరిస్థితులు పొల కార్యకలాపాలకు అనుకూలంగా ఉండవచ్చు.", "hi": "मौसम की स्थिति खेत के काम के लिए अनुकूल हो सकती है।"},
    "Defer non-critical field activities due to expected rainfall.": {"te": "వర్షం వచ్చే అవకాశం ఉన్నందున అత్యవసరం కాని పొల కార్యకలాపాలను వాయిదా వేయండి.", "hi": "बारिश की संभावना के कारण गैर-ज़रूरी खेत के काम टाल दें।"},
    "Rain is expected during part of the day. Carry rain protection.": {"te": "రోజులో కొంతసేపు వర్షం వచ్చే అవకాశం ఉంది. వర్షరక్షణ తీసుకెళ్లండి.", "hi": "दिन के कुछ समय बारिश होने की संभावना है। बारिश से बचाव सामग्री साथ रखें।"},
    "Weather conditions appear suitable for travel plans.": {"te": "వాతావరణ పరిస్థితులు ప్రయాణ ప్రణాళికలకు అనుకూలంగా ఉన్నాయి.", "hi": "मौसम की स्थिति यात्रा योजनाओं के लिए उपयुक्त है।"},
    "Commute conditions appear normal. No special preparations needed.": {"te": "కామ్యూట్ పరిస్థితులు సాధారణంగా ఉన్నాయి. ప్రత్యేక సిద్ధత అవసరం లేదు.", "hi": "यात्रा की स्थिति सामान्य है। किसी विशेष तैयारी की ज़रूरत नहीं है।"},
    "High chance of rain. Outdoor activities may be unfavorable.": {"te": "వర్షం పడే అవకాశం ఎక్కువగా ఉంది. బయట కార్యకలాపాలు అనుకూలంగా ఉండకపోవచ్చు.", "hi": "बारिश होने की अधिक संभावना है। बाहरी गतिविधियाँ अनुकूल नहीं हो सकती हैं।"},
    "Moderate chance of rain. Be prepared for possible showers.": {"te": "వర్షం పడే అవకాశం మితంగా ఉంది. జల్లులకు సిద్ధంగా ఉండండి.", "hi": "बारिश होने की मध्यम संभावना है। संभावित बौछारों के लिए तैयार रहें।"},
    "Thunderstorms possible. Avoid outdoor activities.": {"te": "తుఫానులు వచ్చే అవకాశం ఉంది. బయట కార్యకలాపాలను నివారించండి.", "hi": "तूफ़ान आने की संभावना है। बाहरी गतिविधियों से बचें।"},
    "Warm conditions expected. Ensure adequate water supply for crops.": {"te": "వెచ్చని పరిస్థితులు ఉండవచ్చు. పంటలకు తగినంత నీటి సరఫరా ఉండేలా చూసుకోండి.", "hi": "गर्म परिस्थितियाँ रहने की संभावना है। फसलों के लिए पर्याप्त पानी की व्यवस्था करें।"},
    "High temperatures expected. Monitor crops for heat stress.": {"te": "అధిక ఉష్ణోగ్రతలు ఉండవచ్చు. వేడి ఒత్తిడి కోసం పంటలను పర్యవేక్షించండి.", "hi": "अधिक तापमान रहने की संभावना है। गर्मी के तनाव के लिए फसलों पर नज़र रखें।"},
    "Monitor weather conditions for farming decisions.": {"te": "వ్యవసాయ నిర్ణయాల కోసం వాతావరణ పరిస్థితులను పర్యవేక్షించండి.", "hi": "कृषि निर्णयों के लिए मौसम की परिस्थितियों पर नज़र रखें।"},
    "Strong winds are expected. Exercise additional caution during outdoor travel.": {"te": "బలమైన గాలులు వచ్చే అవకాశం ఉంది. బయట ప్రయాణంలో అదనపు జాగ్రత్త వహించండి.", "hi": "तेज़ हवा आने की संभावना है। बाहरी यात्रा के दौरान अतिरिक्त सावधानी बरतें।"},
    "Thunderstorms possible. Consider rescheduling outdoor travel if possible.": {"te": "తుఫానులు వచ్చే అవకాశం ఉంది. వీలైతే బయట ప్రయాణాన్ని వాయిదా వేయండి.", "hi": "तूफ़ान आने की संभावना है। संभव हो तो बाहरी यात्रा फिर से तय करें।"},
    "Extreme heat expected. Ensure adequate hydration during travel.": {"te": "తీవ్రమైన వేడి ఉండవచ్చు. ప్రయాణంలో తగినంత నీరు తాగండి.", "hi": "अत्यधिक गर्मी रहने की संभावना है। यात्रा के दौरान पर्याप्त पानी पिएँ।"},
    "Rain is possible during the commute. Consider carrying an umbrella.": {"te": "కామ్యూట్ సమయంలో వర్షం వచ్చే అవకాశం ఉంది. గొడుగు తీసుకెళ్లడాన్ని పరిశీలించండి.", "hi": "यात्रा के दौरान बारिश की संभावना है। छाता साथ रखने पर विचार करें।"},
    "Moderate to strong winds expected. Allow extra time for commute.": {"te": "మితమైన నుంచి బలమైన గాలులు వీచవచ్చు. కామ్యూట్‌కి అదనపు సమయం కేటాయించండి.", "hi": "मध्यम से तेज़ हवा चलने की संभावना है। यात्रा के लिए अतिरिक्त समय रखें।"},
    "Extreme heat expected. Stay hydrated during commute.": {"te": "తీవ్రమైన వేడి ఉండవచ్చు. కామ్యూట్ సమయంలో నీరు తాగుతూ ఉండండి.", "hi": "अत्यधिक गर्मी रहने की संभावना है। यात्रा के दौरान पानी पीते रहें।"},
    "Cold conditions expected. Dress warmly for commute.": {"te": "చల్లని పరిస్థితులు ఉండవచ్చు. కామ్యూట్‌కి వెచ్చని దుస్తులు ధరించండి.", "hi": "ठंडी परिस्थितियाँ रहने की संभावना है। यात्रा के लिए गर्म कपड़े पहनें।"},
    "High temperature. Limit outdoor activity duration and use sun protection.": {"te": "ఉష్ణోగ్రత అధికంగా ఉంది. బయట కార్యకలాపాల సమయాన్ని పరిమితం చేసి సూర్యరక్షణ ఉపయోగించండి.", "hi": "तापमान अधिक है। बाहरी गतिविधियों का समय सीमित करें और सूर्य सुरक्षा का उपयोग करें।"},
    "Cold conditions. Dress warmly and limit outdoor exposure time.": {"te": "చల్లని పరిస్థితులు ఉన్నాయి. వెచ్చని దుస్తులు ధరించి బయట గడిపే సమయాన్ని పరిమితం చేయండి.", "hi": "ठंडी परिस्थितियाँ हैं। गर्म कपड़े पहनें और बाहर रहने का समय सीमित करें।"},
    "Weather conditions appear suitable for travel plans.": {"te": "వాతావరణ పరిస్థితులు ప్రయాణ ప్రణాళికలకు అనుకూలంగా ఉన్నాయి.", "hi": "मौसम की स्थिति यात्रा योजनाओं के लिए उपयुक्त है।"},
    "Conditions are generally suitable for outdoor activities.": {"te": "పరిస్థితులు సాధారణంగా బయట కార్యకలాపాలకు అనుకూలంగా ఉన్నాయి.", "hi": "परिस्थितियाँ सामान्य रूप से बाहरी गतिविधियों के लिए उपयुक्त हैं।"},
    "Today in": {"te": "నేడు", "hi": "आज"},
    "will be warm": {"te": "వెచ్చగా ఉంటుంది", "hi": "गर्म रहेगा"},
    "will be pleasant": {"te": "ఆహ్లాదకరంగా ఉంటుంది", "hi": "सुखद रहेगा"},
    "will be cool": {"te": "చల్లగా ఉంటుంది", "hi": "ठंडा रहेगा"},
    "and high likelihood of rain": {"te": "వర్షం పడే అవకాశం ఎక్కువగా ఉంది", "hi": "बारिश की अधिक संभावना है"},
    "and possible rain": {"te": "వర్షం వచ్చే అవకాశం ఉంది", "hi": "बारिश की संभावना है"},
    "and low chance of rain": {"te": "వర్షం పడే అవకాశం తక్కువగా ఉంది", "hi": "बारिश की संभावना कम है"},
    "with low chance of rain": {"te": "వర్షం పడే అవకాశం తక్కువగా ఉంది", "hi": "बारिश की संभावना कम है"},
    "Moderate winds are expected": {"te": "మితమైన గాలులు వీచవచ్చు", "hi": "मध्यम हवा चलने की संभावना है"},
    "Strong winds are expected": {"te": "బలమైన గాలులు వీచవచ్చు", "hi": "तेज़ हवा चलने की संभावना है"},
    "Wear appropriate layers when going outside.": {"te": "బయటకు వెళ్లేటప్పుడు తగిన వెచ్చని దుస్తులు ధరించండి.", "hi": "बाहर जाते समय उपयुक्त गर्म कपड़े पहनें।"},
    "crop, irrigation, and field timing": {"te": "పంటలు, నీటిపారుదల మరియు పొల సమయ ప్రణాళిక", "hi": "फसल, सिंचाई और खेत के काम का समय"},
    "travel timing and route safety": {"te": "ప్రయాణ సమయం మరియు మార్గ భద్రత", "hi": "यात्रा का समय और मार्ग सुरक्षा"},
    "commute timing and rain readiness": {"te": "కామ్యూట్ సమయం మరియు వర్షానికి సిద్ధత", "hi": "यात्रा का समय और बारिश की तैयारी"},
    "outdoor safety and activity planning": {"te": "బయటి భద్రత మరియు కార్యకలాపాల ప్రణాళిక", "hi": "बाहरी सुरक्षा और गतिविधि योजना"},
    "general comfort and safety": {"te": "సాధారణ సౌకర్యం మరియు భద్రత", "hi": "सामान्य सुविधा और सुरक्षा"},
    "mode:": {"te": "మోడ్:", "hi": "मोड:"},
    "focus on": {"te": "దృష్టి:", "hi": "ध्यान:"},
    "general-focused context:": {"te": "సాధారణ మోడ్ సందర్భం:", "hi": "सामान्य मोड संदर्भ:"},
    "Detailed hourly forecast is not available. Check the 7-day forecast for better planning.": {"te": "గంటల వారీ వాతావరణ అంచనా అందుబాటులో లేదు. మెరుగైన ప్రణాళిక కోసం 7 రోజుల అంచనాను చూడండి.", "hi": "घंटेवार पूर्वानुमान उपलब्ध नहीं है। बेहतर योजना के लिए 7-दिन का पूर्वानुमान देखें।"},
    "Weather information is not available.": {"te": "వాతావరణ సమాచారం అందుబాటులో లేదు.", "hi": "मौसम की जानकारी उपलब्ध नहीं है।"},
    "Please ask a weather question so I can check the selected location.": {"te": "ఎంచుకున్న ప్రదేశాన్ని తనిఖీ చేయడానికి వాతావరణ ప్రశ్న అడగండి.", "hi": "चयनित स्थान की जाँच करने के लिए मौसम का प्रश्न पूछें।"},
    "The forecast is not available for": {"te": "కు వాతావరణ అంచనా అందుబాటులో లేదు", "hi": "के लिए पूर्वानुमान उपलब्ध नहीं है"},
    "I can answer about current conditions, the seven-day forecast, rain probability, or the available disaster-risk indicators.": {"te": "ప్రస్తుత పరిస్థితులు, ఏడు రోజుల వాతావరణ అంచనా, వర్షం అవకాశం లేదా అందుబాటులో ఉన్న విపత్తు ప్రమాద సూచికల గురించి నేను సమాధానం ఇవ్వగలను.", "hi": "मैं वर्तमान परिस्थितियों, सात-दिन के पूर्वानुमान, बारिश की संभावना या उपलब्ध आपदा-जोखिम संकेतकों के बारे में उत्तर दे सकता हूँ।"},
    "Checking the latest available weather...": {"te": "తాజా అందుబాటులో ఉన్న వాతావరణాన్ని తనిఖీ చేస్తున్నాం...", "hi": "नवीनतम उपलब्ध मौसम की जाँच की जा रही है..."},
    "The assistant is unavailable right now.": {"te": "సహాయకుడు ప్రస్తుతం అందుబాటులో లేడు.", "hi": "सहायक अभी उपलब्ध नहीं है।"},
    "Best time for outdoor plans": {"te": "బయటి ప్రణాళికలకు ఉత్తమ సమయం", "hi": "बाहरी योजनाओं के लिए सबसे अच्छा समय"},
    "Comfortable window": {"te": "సౌకర్యవంతమైన సమయం", "hi": "आरामदायक समय"},
    "Based on the hourly forecast for the selected location.": {"te": "ఎంచుకున్న స్థలం కోసం గంట వారీ అంచనా ఆధారంగా.", "hi": "चयनित स्थान के लिए प्रति घंटा पूर्वानुमान के आधार पर।"},
}

STATIC_MESSAGE_TRANSLATIONS = {
    "Start voice input": {"te": "వాయిస్ ఇన్‌పుట్ ప్రారంభించండి", "hi": "वॉइस इनपुट शुरू करें"},
    "Stop listening": {"te": "వినడం ఆపండి", "hi": "सुनना बंद करें"},
    "Listening...": {"te": "వింటున్నాం...", "hi": "सुना जा रहा है..."},
    "Voice input is not supported by this browser.": {"te": "ఈ బ్రౌజర్‌లో వాయిస్ ఇన్‌పుట్‌కు మద్దతు లేదు.", "hi": "यह ब्राउज़र वॉइस इनपुट का समर्थन नहीं करता।"},
    "Microphone permission was denied.": {"te": "మైక్రోఫోన్ అనుమతి నిరాకరించబడింది.", "hi": "माइक्रोफ़ोन की अनुमति नहीं मिली।"},
    "No speech was detected. Please try again.": {"te": "మాట్లాడినది గుర్తించలేదు. దయచేసి మళ్లీ ప్రయత్నించండి.", "hi": "कोई आवाज़ नहीं मिली। कृपया फिर प्रयास करें।"},
    "Voice input failed. Text chat is still available.": {"te": "వాయిస్ ఇన్‌పుట్ విఫలమైంది. టెక్స్ట్ చాట్ ఇప్పటికీ అందుబాటులో ఉంది.", "hi": "वॉइस इनपुट विफल हुआ। टेक्स्ट चैट अभी भी उपलब्ध है।"},
    "Reading response aloud...": {"te": "సమాధానాన్ని గట్టిగా చదువుతున్నాం...", "hi": "उत्तर ज़ोर से पढ़ा जा रहा है..."},
    "Voice playback is not available on this device.": {"te": "ఈ పరికరంలో వాయిస్ ప్లేబ్యాక్ అందుబాటులో లేదు.", "hi": "इस डिवाइस पर वॉइस प्लेबैक उपलब्ध नहीं है।"},
    "Read response aloud": {"te": "సమాధానాన్ని గట్టిగా చదవండి", "hi": "उत्तर ज़ोर से पढ़ें"},
    "Stop reading response": {"te": "సమాధానం చదవడం ఆపండి", "hi": "उत्तर पढ़ना बंद करें"},
    "Feature importance is unavailable for this prediction.": {"te": "ఈ అంచనాకు ఫీచర్ ప్రాముఖ్యత అందుబాటులో లేదు.", "hi": "इस अनुमान के लिए फीचर महत्व उपलब्ध नहीं है।"},
    "The prediction uses the available weather inputs; higher-importance factors contribute more to the model estimate.": {"te": "ఈ అంచనా అందుబాటులో ఉన్న వాతావరణ ఇన్‌పుట్‌లను ఉపయోగిస్తుంది; ఎక్కువ ప్రాముఖ్యత ఉన్న కారకాలు మోడల్ అంచనాకు ఎక్కువగా దోహదం చేస్తాయి.", "hi": "यह अनुमान उपलब्ध मौसम इनपुट का उपयोग करता है; अधिक महत्व वाले कारक मॉडल अनुमान में अधिक योगदान देते हैं।"},
    "Simulation only": {"te": "అనుకరణ మాత్రమే", "hi": "केवल सिमुलेशन"},
    "What-If Weather Scenario": {"te": "ఏమైతే వాతావరణ పరిస్థితి", "hi": "क्या-हो-अगर मौसम परिदृश्य"},
    "Explore a possible change without changing the live forecast.": {"te": "లైవ్ అంచనాను మార్చకుండా ఒక సాధ్యమైన మార్పును పరిశీలించండి.", "hi": "लाइव पूर्वानुमान बदले बिना संभावित बदलाव देखें।"},
    "Scenario": {"te": "పరిస్థితి", "hi": "परिदृश्य"},
    "Example: What if rainfall probability becomes 70%?": {"te": "ఉదాహరణ: వర్షం అవకాశం 70% అయితే?", "hi": "उदाहरण: अगर बारिश की संभावना 70% हो जाए तो?"},
    "Simulate": {"te": "అనుకరించండి", "hi": "सिमुलेट करें"},
    "Running simulation...": {"te": "అనుకరణ జరుగుతోంది...", "hi": "सिमुलेशन चल रहा है..."},
    "Simulation unavailable.": {"te": "అనుకరణ అందుబాటులో లేదు.", "hi": "सिमुलेशन उपलब्ध नहीं है।"},
    "Enter a what-if scenario.": {"te": "ఏమైతే పరిస్థితిని నమోదు చేయండి.", "hi": "क्या-हो-अगर परिदृश्य दर्ज करें।"},
    "Include a temperature value in the scenario.": {"te": "పరిస్థితిలో ఉష్ణోగ్రత విలువను చేర్చండి.", "hi": "परिदृश्य में तापमान का मान शामिल करें।"},
    "Use a rainfall or temperature what-if scenario.": {"te": "వర్షపాతం లేదా ఉష్ణోగ్రత ఏమైతే పరిస్థితిని ఉపయోగించండి.", "hi": "बारिश या तापमान का क्या-हो-अगर परिदृश्य उपयोग करें।"},
    "Simulation / What-if scenario — not an actual forecast.": {"te": "అనుకరణ / ఏమైతే పరిస్థితి — ఇది నిజమైన వాతావరణ అంచనా కాదు.", "hi": "सिमुलेशन / क्या-हो-अगर परिदृश्य — यह वास्तविक पूर्वानुमान नहीं है।"},
    "Higher rain probability may disrupt outdoor activities, farming schedules, travel, and commutes.": {"te": "వర్షం అవకాశం పెరిగితే బయట కార్యకలాపాలు, వ్యవసాయ షెడ్యూల్‌లు, ప్రయాణం మరియు కామ్యూట్‌లకు అంతరాయం కలగవచ్చు.", "hi": "बारिश की संभावना बढ़ने से बाहरी गतिविधियों, कृषि कार्यक्रम, यात्रा और रोज़ाना आवागमन में बाधा आ सकती है।"},
    "Higher temperature may increase heat stress and make prolonged outdoor activity less comfortable.": {"te": "అధిక ఉష్ణోగ్రత వేడి ఒత్తిడిని పెంచి, ఎక్కువసేపు బయట కార్యకలాపాలను అసౌకర్యంగా మార్చవచ్చు.", "hi": "अधिक तापमान गर्मी का तनाव बढ़ा सकता है और लंबे समय तक बाहरी गतिविधि को कम आरामदायक बना सकता है।"},
    "Monitor rainfall and irrigation needs before field work.": {"te": "పొల పనికి ముందు వర్షపాతం మరియు నీటిపారుదల అవసరాలను పర్యవేక్షించండి.", "hi": "खेत के काम से पहले बारिश और सिंचाई की ज़रूरतों पर नज़र रखें।"},
    "Allow flexibility for rain or wind during travel.": {"te": "ప్రయాణంలో వర్షం లేదా గాలి కోసం సౌలభ్యాన్ని ఉంచండి.", "hi": "यात्रा के दौरान बारिश या हवा के लिए समय में लचीलापन रखें।"},
    "Check rain readiness and allow extra commute time if needed.": {"te": "వర్షానికి సిద్ధతను పరిశీలించి, అవసరమైతే కామ్యూట్‌కి అదనపు సమయం కేటాయించండి.", "hi": "बारिश की तैयारी जाँचें और ज़रूरत हो तो यात्रा के लिए अतिरिक्त समय रखें।"},
    "Use the rain and heat signals to plan outdoor activity safely.": {"te": "బయటి కార్యకలాపాలను సురక్షితంగా ప్రణాళిక చేయడానికి వర్షం మరియు వేడి సంకేతాలను ఉపయోగించండి.", "hi": "बाहरी गतिविधि की सुरक्षित योजना बनाने के लिए बारिश और गर्मी के संकेतों का उपयोग करें।"},
    "Use the current conditions and forecast to plan your day.": {"te": "మీ రోజును ప్రణాళిక చేయడానికి ప్రస్తుత పరిస్థితులు మరియు అంచనాను ఉపయోగించండి.", "hi": "अपने दिन की योजना बनाने के लिए वर्तमान परिस्थितियों और पूर्वानुमान का उपयोग करें।"},
    "Log in": {"te": "లాగిన్", "hi": "लॉग इन"},
    "AI weather assistant": {"te": "ఎఐ వాతావరణ సహాయకుడు", "hi": "एआई मौसम सहायक"},
    "Suggested questions": {"te": "సూచించిన ప్రశ్నలు", "hi": "सुझाए गए प्रश्न"},
    "Welcome back": {"te": "తిరిగి స్వాగతం", "hi": "वापसी पर स्वागत है"},
    "Return to your outlook.": {"te": "మీ వాతావరణాన్ని తిరిగి చూడండి.", "hi": "अपने मौसम पर वापस जाएँ।"},
    "Email": {"te": "ఇమెయిల్", "hi": "ईमेल"},
    "Password": {"te": "పాస్‌వర్డ్", "hi": "पासवर्ड"},
    "New here?": {"te": "ఇక్కడ కొత్తవారా?", "hi": "यहाँ नए हैं?"},
    "Create an account": {"te": "ఖాతాను సృష్టించండి", "hi": "खाता बनाएँ"},
    "Create account": {"te": "ఖాతా సృష్టించండి", "hi": "खाता बनाएँ"},
    "Join": {"te": "చేరండి", "hi": "जुड़ें"},
    "Create your account.": {"te": "మీ ఖాతాను సృష్టించండి.", "hi": "अपना खाता बनाएँ।"},
    "Save locations and prepare for personalized weather intelligence.": {"te": "స్థలాలను సేవ్ చేసి, వ్యక్తిగత వాతావరణ సమాచారానికి సిద్ధంగా ఉండండి.", "hi": "स्थान सहेजें और व्यक्तिगत मौसम जानकारी के लिए तैयार रहें।"},
    "Name": {"te": "పేరు", "hi": "नाम"},
    "Confirm password": {"te": "పాస్‌వర్డ్ నిర్ధారించండి", "hi": "पासवर्ड की पुष्टि करें"},
    "Already registered?": {"te": "ఇప్పటికే నమోదు చేసుకున్నారా?", "hi": "पहले से पंजीकृत हैं?"},
    "Profile": {"te": "ప్రొఫైల్", "hi": "प्रोफाइल"},
    "Member since": {"te": "సభ్యత్వం ప్రారంభం", "hi": "सदस्य बने"},
    "Open dashboard": {"te": "డాష్‌బోర్డ్ తెరవండి", "hi": "डैशबोर्ड खोलें"},
    "Return home": {"te": "హోమ్‌కు తిరిగి వెళ్లండి", "hi": "होम पर लौटें"},
    "Live intelligence, built for the real world": {"te": "నిజ జీవితానికి రూపొందించిన లైవ్ సమాచారం", "hi": "वास्तविक दुनिया के लिए बनाई गई लाइव जानकारी"},
    "Read the sky": {"te": "ఆకాశాన్ని చదవండి", "hi": "आसमान को समझें"},
    "with clarity.": {"te": "స్పష్టతతో.", "hi": "स्पष्टता के साथ।"},
    "AI-powered weather forecasting and multi-hazard awareness for the moments that matter.": {"te": "ముఖ్యమైన సమయాల కోసం ఎఐ వాతావరణ అంచనా మరియు అనేక ప్రమాదాల అవగాహన.", "hi": "महत्वपूर्ण समय के लिए एआई मौसम पूर्वानुमान और अनेक खतरों की जानकारी।"},
    "Check the outlook": {"te": "వాతావరణాన్ని చూడండి", "hi": "पूर्वानुमान देखें"},
    "Explore the method": {"te": "పద్ధతిని తెలుసుకోండి", "hi": "तरीका जानें"},
    "Partly cloudy": {"te": "పాక్షిక మేఘావృతం", "hi": "आंशिक बादल"},
    "Atmospheric signal stable": {"te": "వాతావరణ సంకేతం స్థిరంగా ఉంది", "hi": "वायुमंडलीय संकेत स्थिर है"},
    "One view, many signals": {"te": "ఒక చూపులో అనేక సంకేతాలు", "hi": "एक नज़र में कई संकेत"},
    "Beyond the forecast.": {"te": "అంచనాకు మించి.", "hi": "पूर्वानुमान से आगे।"},
    "Rainfall prediction": {"te": "వర్షపాతం అంచనా", "hi": "वर्षा पूर्वानुमान"},
    "Flood risk detection": {"te": "వరద ప్రమాద గుర్తింపు", "hi": "बाढ़ जोखिम पहचान"},
    "Heatwave awareness": {"te": "వడగాలుల అవగాహన", "hi": "लू की जानकारी"},
    "Smart alerts": {"te": "తెలివైన హెచ్చరికలు", "hi": "स्मार्ट अलर्ट"},
    "Designed for responsible action": {"te": "బాధ్యతాయుత చర్య కోసం రూపొందించబడింది", "hi": "जिम्मेदार कार्रवाई के लिए बनाया गया"},
    "Signals into": {"te": "సంకేతాలను", "hi": "संकेतों को"},
    "understanding.": {"te": "అవగాహనగా మార్చండి.", "hi": "समझ में बदलें।"},
    "Weather AI home": {"te": "వెదర్ ఎఐ హోమ్", "hi": "मौसम एआई होम"},
    "Main navigation": {"te": "ప్రధాన నావిగేషన్", "hi": "मुख्य नेविगेशन"},
    "Built for clearer decisions in changing weather.": {"te": "మారుతున్న వాతావరణంలో స్పష్టమైన నిర్ణయాల కోసం.", "hi": "बदलते मौसम में स्पष्ट निर्णयों के लिए।"},
    "Unable to update language": {"te": "భాషను నవీకరించలేకపోయాం", "hi": "भाषा अपडेट नहीं हो सकी"},
    "That map location is not valid. Please try again.": {"te": "ఆ మ్యాప్ స్థలం చెల్లదు. దయచేసి మళ్లీ ప్రయత్నించండి.", "hi": "वह मानचित्र स्थान मान्य नहीं है। कृपया फिर प्रयास करें।"},
    "Loading local conditions...": {"te": "స్థానిక పరిస్థితులు లోడ్ అవుతున్నాయి...", "hi": "स्थानीय परिस्थितियाँ लोड हो रही हैं..."},
    "Location services are not supported by this browser.": {"te": "ఈ బ్రౌజర్‌లో స్థల సేవలకు మద్దతు లేదు.", "hi": "यह ब्राउज़र स्थान सेवाओं का समर्थन नहीं करता।"},
    "Requesting your location...": {"te": "మీ స్థలాన్ని కోరుతున్నాం...", "hi": "आपका स्थान माँगा जा रहा है..."},
    "Location permission was denied. You can still select a point on the map.": {"te": "స్థల అనుమతి నిరాకరించబడింది. మీరు మ్యాప్‌లో ఒక బిందువును ఎంచుకోవచ్చు.", "hi": "स्थान की अनुमति नहीं मिली। आप अभी भी मानचित्र पर एक बिंदु चुन सकते हैं।"},
    "Your location could not be determined. Please try again or select a point on the map.": {"te": "మీ స్థలాన్ని గుర్తించలేకపోయాం. మళ్లీ ప్రయత్నించండి లేదా మ్యాప్‌లో ఒక బిందువును ఎంచుకోండి.", "hi": "आपका स्थान निर्धारित नहीं हो सका। फिर प्रयास करें या मानचित्र पर एक बिंदु चुनें।"},
    "Failed to update mode.": {"te": "మోడ్‌ను నవీకరించలేకపోయాం.", "hi": "मोड अपडेट नहीं हो सका।"},
    "Account created. You can now log in.": {"te": "ఖాతా సృష్టించబడింది. ఇప్పుడు లాగిన్ చేయవచ్చు.", "hi": "खाता बन गया है। अब आप लॉग इन कर सकते हैं।"},
    "Welcome back,": {"te": "తిరిగి స్వాగతం,", "hi": "वापसी पर स्वागत है,"},
    "Name is required.": {"te": "పేరు అవసరం.", "hi": "नाम आवश्यक है।"},
    "Enter a valid email address.": {"te": "చెల్లుబాటు అయ్యే ఇమెయిల్ చిరునామాను నమోదు చేయండి.", "hi": "मान्य ईमेल पता दर्ज करें।"},
    "Password must be at least 8 characters long.": {"te": "పాస్‌వర్డ్ కనీసం 8 అక్షరాలు ఉండాలి.", "hi": "पासवर्ड कम से कम 8 वर्णों का होना चाहिए।"},
    "Passwords do not match.": {"te": "పాస్‌వర్డ్‌లు సరిపోలడం లేదు.", "hi": "पासवर्ड मेल नहीं खाते।"},
    "An account with that email already exists.": {"te": "ఆ ఇమెయిల్‌తో ఖాతా ఇప్పటికే ఉంది.", "hi": "उस ईमेल से खाता पहले से मौजूद है।"},
    "Rain Expected": {"te": "వర్షం వచ్చే అవకాశం ఉంది", "hi": "बारिश होने की संभावना है"},
    "No Rain Expected": {"te": "వర్షం వచ్చే అవకాశం లేదు", "hi": "बारिश होने की संभावना नहीं है"},
    "Critical": {"te": "తీవ్రమైన", "hi": "गंभीर"},
    "High": {"te": "అధిక", "hi": "उच्च"},
    "Moderate": {"te": "మితమైన", "hi": "मध्यम"},
    "Low": {"te": "తక్కువ", "hi": "कम"},
    "This is an AI estimate based on historical weather patterns, not an official forecast.": {"te": "ఇది చారిత్రక వాతావరణ నమూనాల ఆధారిత ఎఐ అంచనా, అధికారిక వాతావరణ అంచనా కాదు.", "hi": "यह ऐतिहासिक मौसम पैटर्न पर आधारित एआई अनुमान है, आधिकारिक पूर्वानुमान नहीं।"},
    "AI rainfall prediction is currently unavailable.": {"te": "ఎఐ వర్షపాతం అంచనా ప్రస్తుతం అందుబాటులో లేదు.", "hi": "एआई वर्षा पूर्वानुमान अभी उपलब्ध नहीं है।"},
    "Interactive map for selected location": {"te": "ఎంచుకున్న స్థలానికి ఇంటరాక్టివ్ మ్యాప్", "hi": "चयनित स्थान का इंटरैक्टिव मानचित्र"},
    "Select anywhere on the map to explore local conditions.": {"te": "స్థానిక పరిస్థితులను చూడటానికి మ్యాప్‌లో ఎక్కడైనా ఎంచుకోండి.", "hi": "स्थानीय परिस्थितियाँ देखने के लिए मानचित्र पर कहीं भी चुनें।"},
    "Selected location": {"te": "ఎంచుకున్న స్థలం", "hi": "चयनित स्थान"},
    "Coordinates": {"te": "కోఆర్డినేట్లు", "hi": "निर्देशांक"},
    "Search for a city to load its live conditions.": {"te": "లైవ్ పరిస్థితులను లోడ్ చేయడానికి నగరం కోసం వెతకండి.", "hi": "लाइव परिस्थितियाँ लोड करने के लिए शहर खोजें।"},
    "Elevated runoff and drainage stress likely.": {"te": "నీటి ప్రవాహం మరియు డ్రైనేజీపై ఒత్తిడి పెరగవచ్చు.", "hi": "अधिक जल बहाव और जल निकासी पर दबाव की संभावना है।"},
    "Conditions remain manageable at the moment.": {"te": "ప్రస్తుతానికి పరిస్థితులు నియంత్రణలో ఉన్నాయి.", "hi": "फिलहाल परिस्थितियाँ नियंत्रण में हैं।"},
    "Heat burden is elevated; stay hydrated and limit peak exposure.": {"te": "వేడి ప్రభావం ఎక్కువగా ఉంది; నీరు తాగుతూ, తీవ్ర వేడికి దూరంగా ఉండండి.", "hi": "गर्मी का प्रभाव अधिक है; पानी पीते रहें और तेज़ धूप से बचें।"},
    "No significant heat stress indicated by current readings.": {"te": "ప్రస్తుత కొలతల్లో గణనీయమైన వేడి ఒత్తిడి కనిపించలేదు.", "hi": "वर्तमान मापों में गर्मी का महत्वपूर्ण तनाव नहीं दिखता।"},
    "Rain intensity may affect travel and drainage.": {"te": "వర్ష తీవ్రత ప్రయాణం మరియు డ్రైనేజీని ప్రభావితం చేయవచ్చు.", "hi": "बारिश की तीव्रता यात्रा और जल निकासी को प्रभावित कर सकती है।"},
    "Forecast precipitation remains relatively stable.": {"te": "వర్షపాతం అంచనా తులనాత్మకంగా స్థిరంగా ఉంది.", "hi": "पूर्वानुमानित वर्षा अपेक्षाकृत स्थिर है।"},
    "The weather service is temporarily unavailable.": {"te": "వాతావరణ సేవ తాత్కాలికంగా అందుబాటులో లేదు.", "hi": "मौसम सेवा अस्थायी रूप से उपलब्ध नहीं है।"},
    "Enter a city or town to search.": {"te": "వెతకడానికి నగరం లేదా పట్టణం నమోదు చేయండి.", "hi": "खोजने के लिए शहर या कस्बा दर्ज करें।"},
    "We could not find that city or town.": {"te": "ఆ నగరం లేదా పట్టణం కనుగొనలేకపోయాం.", "hi": "वह शहर या कस्बा नहीं मिल सका।"},
    "The location response was incomplete.": {"te": "స్థల సమాచారం అసంపూర్ణంగా ఉంది.", "hi": "स्थान की जानकारी अधूरी है।"},
    "We could not identify that map location.": {"te": "ఆ మ్యాప్ స్థలాన్ని గుర్తించలేకపోయాం.", "hi": "उस मानचित्र स्थान की पहचान नहीं हो सकी।"},
    "The weather response was incomplete.": {"te": "వాతావరణ సమాచారం అసంపూర్ణంగా ఉంది.", "hi": "मौसम की जानकारी अधूरी है।"},
    "The forecast response was incomplete.": {"te": "వాతావరణ అంచనా సమాచారం అసంపూర్ణంగా ఉంది.", "hi": "पूर्वानुमान की जानकारी अधूरी है।"},
    "The selected map coordinates are invalid.": {"te": "ఎంచుకున్న మ్యాప్ కోఆర్డినేట్లు చెల్లవు.", "hi": "चयनित मानचित्र निर्देशांक अमान्य हैं।"},
    "Enter valid map coordinates.": {"te": "చెల్లుబాటు అయ్యే మ్యాప్ కోఆర్డినేట్లను నమోదు చేయండి.", "hi": "मान्य मानचित्र निर्देशांक दर्ज करें।"},
    "Please log in.": {"te": "దయచేసి లాగిన్ చేయండి.", "hi": "कृपया लॉग इन करें।"},
    "Please log in to use the weather assistant.": {"te": "వాతావరణ సహాయకుడిని ఉపయోగించడానికి లాగిన్ చేయండి.", "hi": "मौसम सहायक का उपयोग करने के लिए लॉग इन करें।"},
    "Please log in to view your dashboard.": {"te": "మీ డాష్‌బోర్డ్‌ను చూడటానికి లాగిన్ చేయండి.", "hi": "अपना डैशबोर्ड देखने के लिए लॉग इन करें।"},
    "Please log in to view your profile.": {"te": "మీ ప్రొఫైల్‌ను చూడటానికి లాగిన్ చేయండి.", "hi": "अपनी प्रोफाइल देखने के लिए लॉग इन करें।"},
    "Ask a weather question to continue.": {"te": "కొనసాగించడానికి వాతావరణ ప్రశ్న అడగండి.", "hi": "जारी रखने के लिए मौसम का प्रश्न पूछें।"},
    "Select a location before asking a question.": {"te": "ప్రశ్న అడగడానికి ముందు ఒక స్థలాన్ని ఎంచుకోండి.", "hi": "प्रश्न पूछने से पहले स्थान चुनें।"},
    "Select a location first.": {"te": "ముందుగా ఒక స్థలాన్ని ఎంచుకోండి.", "hi": "पहले स्थान चुनें।"},
    "Language updated successfully": {"te": "భాష విజయవంతంగా నవీకరించబడింది", "hi": "भाषा सफलतापूर्वक अपडेट की गई"},
    "Mode updated successfully": {"te": "మోడ్ విజయవంతంగా నవీకరించబడింది", "hi": "मोड सफलतापूर्वक अपडेट किया गया"},
    "Invalid email or password.": {"te": "ఇమెయిల్ లేదా పాస్‌వర్డ్ చెల్లదు.", "hi": "ईमेल या पासवर्ड अमान्य है।"},
    "You have been logged out.": {"te": "మీరు లాగ్ అవుట్ అయ్యారు.", "hi": "आप लॉग आउट हो गए हैं।"},
    "The page you requested was not found.": {"te": "మీరు కోరిన పేజీ కనుగొనబడలేదు.", "hi": "आपके द्वारा अनुरोधित पृष्ठ नहीं मिला।"},
    "Something went wrong on our side.": {"te": "మా వైపు సమస్య ఏర్పడింది.", "hi": "हमारी ओर से कुछ समस्या हुई।"},
}


# ---------------------------------------------------------------------------
# Phase 8 centralized translation pipeline.
#
# The pipeline deliberately avoids word-by-word replacement of composed
# messages. Word-by-word replacement produced mixed-language output such as
# "AI వర్షపాతం Prediction". The rules are:
#   1. Exact full-string translations win.
#   2. Structured sentence templates localize dynamic model-generated text
#      while preserving numbers, units and location names.
#   3. Longer messages are localized only when every sentence has a complete
#      translation.
#   4. Anything that cannot be fully localized stays entirely in English
#      (never a mixture).
# ---------------------------------------------------------------------------

EXTRA_MESSAGES = {
    "Weather icon": {"te": "వాతావరణ చిహ్నం", "hi": "मौसम आइकन"},
    "Voice input is not supported in this browser. Please use a supported browser or type your question.": {
        "te": "ఈ బ్రౌజర్‌లో వాయిస్ ఇన్‌పుట్‌కు మద్దతు లేదు. మద్దతు ఉన్న బ్రౌజర్‌ను ఉపయోగించండి లేదా మీ ప్రశ్నను టైప్ చేయండి.",
        "hi": "यह ब्राउज़र वॉइस इनपुट का समर्थन नहीं करता। कृपया समर्थित ब्राउज़र उपयोग करें या अपना प्रश्न टाइप करें।",
    },
    "The network connection was lost during voice input. Please try again.": {
        "te": "వాయిస్ ఇన్‌పుట్ సమయంలో నెట్‌వర్క్ కనెక్షన్ కోల్పోయింది. మళ్లీ ప్రయత్నించండి.",
        "hi": "वॉइस इनपुट के दौरान नेटवर्क कनेक्शन टूट गया। कृपया फिर प्रयास करें।",
    },
    "Your microphone could not be used. Check audio settings and try again.": {
        "te": "మీ మైక్రోఫోన్‌ను ఉపయోగించలేకపోయాం. ఆడియో సెట్టింగ్‌లను తనిఖీ చేసి మళ్లీ ప్రయత్నించండి.",
        "hi": "आपका माइक्रोफ़ोन उपयोग नहीं हो सका। ऑडियो सेटिंग्स जाँचें और फिर प्रयास करें।",
    },
    "Speech could not be understood. Please try again.": {
        "te": "మీ మాట అర్థం కాలేదు. మళ్లీ ప్రయత్నించండి.",
        "hi": "आपकी बात समझी नहीं जा सकी। कृपया फिर प्रयास करें।",
    },
    "Voice input was canceled.": {
        "te": "వాయిస్ ఇన్‌పుట్ రద్దు చేయబడింది.",
        "hi": "वॉइस इनपुट रद्द कर दिया गया।",
    },
    "A voice for the selected language is not available on this device. The text answer is still available.": {
        "te": "ఈ పరికరంలో ఎంచుకున్న భాషకు వాయిస్ అందుబాటులో లేదు. టెక్స్ట్ సమాధానం ఇప్పటికీ అందుబాటులో ఉంది.",
        "hi": "इस डिवाइस पर चुनी गई भाषा के लिए वॉइस उपलब्ध नहीं है। टेक्स्ट उत्तर अभी भी उपलब्ध है।",
    },
"Heavier rainfall is expected. Consider postponing non-essential outdoor activities.": {
        "te": "భారీ వర్షం వచ్చే అవకాశం ఉంది. అవసరం లేని బయటి కార్యకలాపాలను వాయిదా వేయండి.",
        "hi": "भारी बारिश की आशंका है। अनावश्यक बाहरी गतिविधियों को टालें।",
    },
    "Extremely high temperatures are expected. Stay hydrated and avoid prolonged outdoor exposure.": {
        "te": "అత్యంత అధిక ఉష్ణోగ్రతలు వచ్చే అవకాశం ఉంది. నీరు తాగుతూ ఉండండి మరియు ఎక్కువసేపు ఎండలో ఉండకండి.",
        "hi": "अत्यधिक उच्च तापमान की संभावना है। पानी पीते रहें और लंबे समय तक धूप में न रहें।",
    },
    "Warm temperatures are expected. Use sun protection if going outside.": {
        "te": "వెచ్చని ఉష్ణోగ్రతలు వచ్చే అవకాశం ఉంది. బయటకు వెళ్తే సూర్యరక్షణ ఉపయోగించండి.",
        "hi": "गर्म तापमान की संभावना है। बाहर जाते समय सूर्य सुरक्षा का उपयोग करें।",
    },
    "Strong winds are expected. Exercise caution during outdoor activities.": {
        "te": "బలమైన గాలులు వచ్చే అవకాశం ఉంది. బయటి కార్యకలాపాల్లో జాగ్రత్తగా ఉండండి.",
        "hi": "तेज़ हवाएँ चलने की संभावना है। बाहरी गतिविधियों में सावधानी बरतें।",
    },
    "Moderate winds are expected. Be cautious if traveling.": {
        "te": "మితమైన గాలులు వచ్చే అవకాశం ఉంది. ప్రయాణిస్తున్నప్పుడు జాగ్రత్తగా ఉండండి.",
        "hi": "मध्यम हवाएँ चलने की संभावना है। यात्रा करते समय सावधान रहें।",
    },
    "Thunderstorms are possible. Avoid outdoor activities and secure loose objects.": {
        "te": "తుఫానులు వచ్చే అవకాశం ఉంది. బయటి కార్యకలాపాలకు దూరంగా ఉండి వదులుగా ఉన్న వస్తువులను భద్రపరచండి.",
        "hi": "तूफ़ान आ सकते हैं। बाहरी गतिविधियों से बचें और खुले सामान को सुरक्षित करें।",
    },
    "Weather conditions may not be favorable for outdoor activities.": {
        "te": "బయటి కార్యకలాపాలకు వాతావరణ పరిస్థితులు అనుకూలంగా ఉండకపోవచ్చు.",
        "hi": "बाहरी गतिविधियों के लिए मौसम की स्थितियाँ अनुकूल नहीं हो सकती हैं।",
    },
    "Rain and wind are expected. Exercise extra caution during travel.": {
        "te": "వర్షం మరియు గాలి వచ్చే అవకాశం ఉంది. ప్రయాణంలో అదనపు జాగ్రత్త తీసుకోండి.",
        "hi": "बारिश और हवा की संभावना है। यात्रा के दौरान अतिरिक्त सावधानी बरतें।",
    },
    "Carry rain protection if going outside.": {
        "te": "బయటకు వెళ్లేటప్పుడు వర్షరక్షణ తీసుకెళ్లండి.",
        "hi": "बाहर जाते समय बारिश से बचाव सामग्री साथ रखें।",
    },
    "Use sun protection if going outside.": {
        "te": "బయటకు వెళ్లేటప్పుడు సూర్యరక్షణ ఉపయోగించండి.",
        "hi": "बाहर जाते समय सूर्य सुरक्षा का उपयोग करें।",
    },
    "Adequate precipitation detected. Check irrigation needs.": {
        "te": "తగినంత వర్షపాతం గుర్తించబడింది. నీటిపారుదల అవసరాలను తనిఖీ చేయండి.",
        "hi": "पर्याप्त वर्षा हुई है। सिंचाई की आवश्यकता जाँचें।",
    },
    "No significant rainfall expected. Consider irrigation planning.": {
        "te": "గణనీయమైన వర్షపాతం వచ్చే అవకాశం లేదు. నీటిపారుదల ప్రణాళికను పరిశీలించండి.",
        "hi": "महत्वपूर्ण बारिश की संभावना नहीं है। सिंचाई की योजना पर विचार करें।",
    },
"High temperatures expected. Monitor crops for heat stress.": {
        "te": "అధిక ఉష్ణోగ్రతలు వచ్చే అవకాశం ఉంది. పంటలను వేడి ఒత్తిడి కోసం పర్యవేక్షించండి.",
        "hi": "उच्च तापमान की संभावना है। गर्मी के तनाव के लिए फसलों की निगरानी करें।",
    },
    "Warm conditions expected. Ensure adequate water supply for crops.": {
        "te": "వెచ్చని పరిస్థితులు వచ్చే అవకాశం ఉంది. పంటలకు తగినంత నీరు ఉండేలా చూసుకోండి.",
        "hi": "गर्म स्थितियों की संभावना है। फसलों के लिए पर्याप्त जल आपूर्ति सुनिश्चित करें।",
    },
    "Weather conditions may be favorable for field activities.": {
        "te": "పొల పనులకు వాతావరణ పరిస్థితులు అనుకూలంగా ఉండవచ్చు.",
        "hi": "खेत के कामों के लिए मौसम की स्थितियाँ अनुकूल हो सकती हैं।",
    },
    "Defer non-critical field activities due to expected rainfall.": {
        "te": "వర్షపాతం అంచనా ఉన్న నేపథ్యంలో అవసరం లేని పొల పనులను వాయిదా వేయండి.",
        "hi": "बारिश की संभावना के कारण गैर-आवश्यक खेत के काम स्थगित करें।",
    },
    "Monitor weather conditions for farming decisions.": {
        "te": "వ్యవసాయ నిర్ణయాల కోసం వాతావరణ పరిస్థితులను పర్యవేక్షించండి.",
        "hi": "कृषि निर्णयों के लिए मौसम की स्थितियों पर नज़र रखें।",
    },
    "Weather information is not available for farming guidance.": {
        "te": "వ్యవసాయ మార్గదర్శనానికి వాతావరణ సమాచారం అందుబాటులో లేదు.",
        "hi": "कृषि मार्गदर्शन के लिए मौसम की जानकारी उपलब्ध नहीं है।",
    },
    "Rain is expected during part of the day. Carry rain protection.": {
        "te": "రోజులో కొంత భాగం వర్షం వచ్చే అవకాశం ఉంది. వర్షరక్షణ తీసుకెళ్లండి.",
        "hi": "दिन के कुछ समय बारिश होने की संभावना है। बारिश से बचाव सामग्री साथ रखें।",
    },
    "Strong winds are expected. Exercise additional caution during outdoor travel.": {
        "te": "బలమైన గాలులు వచ్చే అవకాశం ఉంది. బయటి ప్రయాణంలో అదనపు జాగ్రత్త తీసుకోండి.",
        "hi": "तेज़ हवाओं की संभावना है। बाहरी यात्रा के दौरान अतिरिक्त सावधानी बरतें।",
    },
    "Thunderstorms possible. Consider rescheduling outdoor travel if possible.": {
        "te": "తుఫానులు వచ్చే అవకాశం ఉంది. వీలైతే బయటి ప్రయాణాలను వాయిదా వేయడం పరిశీలించండి.",
        "hi": "तूफ़ान संभव हैं। हो सके तो बाहरी यात्रा को पुनर्निर्धारित करने पर विचार करें।",
    },
    "Extreme heat expected. Ensure adequate hydration during travel.": {
        "te": "తీవ్రమైన వేడి వచ్చే అవకాశం ఉంది. ప్రయాణంలో తగినంత నీరు తాగుతూ ఉండండి.",
        "hi": "भीषण गर्मी की संभावना है। यात्रा के दौरान पर्याप्त पानी पीते रहें।",
    },
    "Weather information is not available for travel planning.": {
        "te": "ప్రయాణ ప్రణాళికకు వాతావరణ సమాచారం అందుబాటులో లేదు.",
        "hi": "यात्रा योजना के लिए मौसम की जानकारी उपलब्ध नहीं है।",
    },
"Rain is possible during the commute. Consider carrying an umbrella.": {
        "te": "కామ్యూట్ సమయంలో వర్షం వచ్చే అవకాశం ఉంది. గొడుగు తీసుకెళ్లడం పరిశీలించండి.",
        "hi": "यात्रा के दौरान बारिश की संभावना है। छाता साथ रखने पर विचार करें।",
    },
    "Moderate to strong winds expected. Allow extra time for commute.": {
        "te": "మితమైన నుండి బలమైన గాలులు వచ్చే అవకాశం ఉంది. కామ్యూట్‌కి అదనపు సమయం తీసుకోండి.",
        "hi": "मध्यम से तेज़ हवा की संभावना है। यात्रा के लिए अतिरिक्त समय रखें।",
    },
    "Extreme heat expected. Stay hydrated during commute.": {
        "te": "తీవ్రమైన వేడి వచ్చే అవకాశం ఉంది. కామ్యూట్ సమయంలో నీరు తాగుతూ ఉండండి.",
        "hi": "भीषण गर्मी की संभावना है। यात्रा के दौरान पानी पीते रहें।",
    },
    "Cold conditions expected. Dress warmly for commute.": {
        "te": "చల్లని పరిస్థితులు వచ్చే అవకాశం ఉంది. కామ్యూట్‌కు వెచ్చగా దుస్తులు ధరించండి.",
        "hi": "ठंडी स्थितियों की संभावना है। यात्रा के लिए गर्म कपड़े पहनें।",
    },
    "Commute conditions appear normal. No special preparations needed.": {
        "te": "కామ్యూట్ పరిస్థితులు సాధారణంగా ఉన్నాయి. ప్రత్యేక సన్నాహాలు అవసరం లేదు.",
        "hi": "यात्रा की स्थितियाँ सामान्य हैं। कोई विशेष तैयारी आवश्यक नहीं है।",
    },
    "Weather information is not available for commute planning.": {
        "te": "కామ్యూట్ ప్రణాళికకు వాతావరణ సమాచారం అందుబాటులో లేదు.",
        "hi": "यात्रा योजना के लिए मौसम की जानकारी उपलब्ध नहीं है।",
    },
    "Moderate chance of rain. Be prepared for possible showers.": {
        "te": "మితమైన వర్షం అవకాశం ఉంది. అవకాశం ఉన్న జల్లులకు సిద్ధంగా ఉండండి.",
        "hi": "बारिश की मध्यम संभावना है। संभावित बौछारों के लिए तैयार रहें।",
    },
    "Thunderstorms possible. Avoid outdoor activities.": {
        "te": "తుఫానులు వచ్చే అవకాశం ఉంది. బయటి కార్యకలాపాలకు దూరంగా ఉండండి.",
        "hi": "तूफ़ान संभव हैं। बाहरी गतिविधियों से बचें।",
    },
    "Strong winds expected. Avoid exposure during outdoor activities.": {
        "te": "బలమైన గాలులు వచ్చే అవకాశం ఉంది. బయటి కార్యకలాపాల్లో వాటికి గురికాకుండా ఉండండి.",
        "hi": "तेज़ हवाओं की संभावना है। बाहरी गतिविधियों में इनके संपर्क से बचें।",
    },
    "Extreme heat. Outdoor activities not recommended.": {
        "te": "తీవ్రమైన వేడి. బయటి కార్యకలాపాలు సిఫార్సు చేయబడవు.",
        "hi": "भीषण गर्मी। बाहरी गतिविधियों की अनुशंसा नहीं की जाती।",
    },
    "High temperature. Limit outdoor activity duration and use sun protection.": {
        "te": "అధిక ఉష్ణోగ్రత. బయటి కార్యకలాపాల సమయాన్ని పరిమితం చేసి సూర్యరక్షణ ఉపయోగించండి.",
        "hi": "उच्च तापमान। बाहरी गतिविधि की अवधि सीमित करें और सूर्य सुरक्षा का उपयोग करें।",
    },
    "Weather information is not available for activity planning.": {
        "te": "కార్యకలాపాల ప్రణాళికకు వాతావరణ సమాచారం అందుబాటులో లేదు.",
        "hi": "गतिविधि योजना के लिए मौसम की जानकारी उपलब्ध नहीं है।",
    },
    "Weather information is not available to suggest a best time window.": {
        "te": "ఉత్తమ సమయాన్ని సూచించడానికి వాతావరణ సమాచారం అందుబాటులో లేదు.",
        "hi": "सर्वोत्तम समय सुझाने के लिए मौसम की जानकारी उपलब्ध नहीं है।",
    },
    "Cold conditions. Dress warmly and limit outdoor exposure time.": {
        "te": "చల్లని పరిస్థితులు. వెచ్చగా దుస్తులు ధరించి, బయట గడిపే సమయాన్ని పరిమితం చేయండి.",
        "hi": "ठंडी स्थितियाँ। गर्म कपड़े पहनें और बाहर रहने का समय सीमित करें।",
    },
    "Cold conditions expected. Dress warmly and limit outdoor exposure time.": {
        "te": "చల్లని పరిస్థితులు వచ్చే అవకాశం ఉంది. వెచ్చగా దుస్తులు ధరించి, బయట గడిపే సమయాన్ని పరిమితం చేయండి.",
        "hi": "ठंडी स्थितियों की संभावना है। गर्म कपड़े पहनें और बाहर रहने का समय सीमित करें।",
    },
    "Warm conditions expected": {"te": "వెచ్చని పరిస్థితులు వచ్చే అవకాశం", "hi": "गर्म स्थितियों की संभावना"},
    "High chance of rainfall is expected. Carry rain protection.": {
        "te": "అధిక వర్షం అవకాశం ఉంది. వర్షరక్షణ తీసుకెళ్లండి.",
        "hi": "बारिश की अधिक संभावना है। बारिश से बचाव सामग्री साथ रखें।",
    },
}

# Phase 3: personalization and delivery sentences used by the assistant,
# the scheduler-driven email body, and the profile delivery-status panel.
PHASE3_MESSAGES = {
    "Rain probability today is {value}%.": {
        "te": "ఈరోజు వర్ష సంభావ్యత {value}%.",
        "hi": "आज बारिश की संभावना {value}% है।",
    },
    "Rain probability is unavailable.": {
        "te": "వర్ష సంభావ్యత అందుబాటులో లేదు.",
        "hi": "बारिश की संभावना उपलब्ध नहीं है।",
    },
    "Temperature is {value}°C.": {"te": "ఉష్ణోగ్రత {value}°C.", "hi": "तापमान {value}°C है।"},
    "Temperature is {value}°C": {"te": "ఉష్ణోగ్రత {value}°C", "hi": "तापमान {value}°C"},
    "The ML rainfall estimate is {value}%.": {
        "te": "ML వర్ష అంచనా {value}%.",
        "hi": "ML वर्षा अनुमान {value}% है।",
    },
    "Flood risk is {value}, so drainage and field access need attention.": {
        "te": "వరద ప్రమాదం {value}, కాబట్టి నీటి నిర్గమం మరియు పొలం ప్రవేశం గమనించండి.",
        "hi": "बाढ़ का जोखिम {value} है, इसलिए जल निकासी और खेत की पहुँच पर ध्यान दें।",
    },
    "Field heat exposure is high, so schedule heavier work in cooler hours.": {
        "te": "పొలంలో అధిక ఉష్ణత, కాబట్టి పనిని చల్లని సమయాల్లో చేయండి.",
        "hi": "खेत में गर्मी अधिक है, इसलिए भारी काम ठंडे समय में करें।",
    },
    "Heatwave conditions are present; irrigate early and avoid midday fieldwork.": {
        "te": "వేడి ఉష్ణోగ్రత పరిస్థితులు ఉన్నాయి; తెల్లవారుజాముననే నీరు పెట్టి మధ్యాహ్నం పనులు ఎతవండి.",
        "hi": "लू की स्थिति है; सुबह जल्दी सिंचाई करें और दोपहर के खेत के काम से बचें।",
    },
    "Wind is strong at {value} km/h, which may affect travel comfort.": {
        "te": "{value} కి.మీ./గంట గాలి బలంగా ఉంది, ఇది ప్రయాణ సౌకర్యాన్ని ప్రభావితం చేయవచ్చు.",
        "hi": "{value} किमी/घंटे की तेज़ हवा है, जो यात्रा को प्रभावित कर सकती है।",
    },
    "Heavy-rain risk is {value}, so allow buffer time.": {
        "te": "భారీ వర్ష ప్రమాదం {value}, కాబట్టి అదనపు సమయం పెట్టుకోండి.",
        "hi": "भारी बारिश का जोखिम {value} है, इसलिए अतिरिक्त समय रखें।",
    },
    "Avoid low-lying routes while flood risk is elevated.": {
        "te": "వరద ప్రమాదం ఎక్కువగా ఉన్నప్పుడు నీటి మర్గాలను నివారించండి.",
        "hi": "बाढ़ का जोखिम बढ़ने पर निचले इलाकों के रास्तों से बचें।",
    },
    "Wind at {value} km/h may slow the commute.": {
        "te": "{value} కి.మీ./గంట గాలి ప్రయాణాన్ని దాదాపు ఆలస్యం కలిగించవచ్చు.",
        "hi": "{value} किमी/घंटे की हवा यात्रा को धीमा कर सकती है।",
    },
    "Current conditions are {value}.": {"te": "ప్రస్తుత పరిస్థితులు {value}.", "hi": "वर्तमान स्थिति {value} है।"},
    "Wind is strong, so secure loose items before going out.": {
        "te": "గాలి బలంగా ఉంది, కాబట్టి బయటకు వెళ్లే ముందు విచిలిన వస్తువులను కాపాడండి.",
        "hi": "हवा तेज़ है, बाहर जाने से पहले ढीली चीज़ें सुरक्षित रखें।",
    },
    "Heat stress is high, so prefer the cooler parts of the day.": {
        "te": "గాఢమ్మైన ఉష్ణత ఎక్కువగా ఉంది, కాబట్టి రోజు చల్లని సమయాన్ని ఎంచుకోండి.",
        "hi": "गर्मी अधिक है, इसलिए दिन के ठंडे समय का चुनाव करें।",
    },
    "The rule-based risk outlook flags {value}.": {
        "te": "నియమాధారిత ప్రమాద అంచనా {value} అని సూచిస్తోంది.",
        "hi": "नियम-आधारित जोखिम अनुमान {value} बताता है।",
    },
    "Active alerts: {value}.": {
        "te": "ప్రస్తుత అలర్ట్‌లు: {value}.",
        "hi": "सक्रिय अलर्ट: {value}।",
    },
    "Conditions are stable; use the forecast to plan your day.": {
        "te": "పరిస్థితులు స్థిరంగా ఉన్నాయి; రోజు ప్రణాళిక కోసం అంచనా వాడండి.",
        "hi": "स्थिति स्थिर है; दिन की योजना के लिए पूर्वानुमान का उपयोग करें।",
    },
    # Delivery / preference panel labels
    "Email alerts": {"te": "ఈమెయిల్ అలర్ట్‌లు", "hi": "ईमेल अलर्ट"},
    "SMS alerts": {"te": "ఎస్‌ఎమ్‌ఎస్ అలర్ట్‌లు", "hi": "एसएमएस अलर्ट"},
    "Phone number for SMS": {"te": "ఎస్‌ఎమ్‌ఎస్ కోసం ఫోన్ నంబర్", "hi": "एसएमएस के लिए फ़ोन नंबर"},
    "Preferred language": {"te": "ప్రిఫర్ చేసిన భాష", "hi": "पसंदीदा भाषा"},
    "Preferred weather mode": {"te": "ప్రిఫర్ చేసిన వాతావరణ మోడ్", "hi": "पसंदीदा मौसम मोड"},
    "Delivery status": {"te": "డెలివరీ స్థితి", "hi": "डिलीवरी स्थिति"},
    "Email": {"te": "ఈమెయిల్", "hi": "ईमेल"},
    "SMS": {"te": "ఎస్‌ఎమ్‌ఎస్", "hi": "एसएमएस"},
    "Enabled": {"te": "ప్రారంభించబడింది", "hi": "सक्षम"},
    "Disabled": {"te": "నిలిపివేయబడింది", "hi": "बंद"},
    "Server configured": {"te": "సర్వర్ కాన్ఫిగర్ అయింది", "hi": "सर्वर कॉन्फ़िगर है"},
    "No mail server configured yet": {
        "te": "మెయిల్ సర్వర్ ఇంకా కాన్ఫిగర్ కాలేదు",
        "hi": "मेल सर्वर अभी कॉन्फ़िगर नहीं है",
    },
    "No SMS provider configured yet": {
        "te": "ఎస్‌ఎమ్‌ఎస్ ప్రైడర్ ఇంకా కాన్ఫిగర్ కాలేదు",
        "hi": "एसएमएस प्रदाता अभी कॉन्फ़िगर नहीं है",
    },
}

# All exact, complete translations merged into a single lookup table.
_ALL_TRANSLATION_TABLES = (
    ALERT_TYPE_TRANSLATIONS,
    SEVERITY_TRANSLATIONS,
    WEATHER_CONDITION_TRANSLATIONS,
    COMMON_TRANSLATIONS,
    MODE_NAME_TRANSLATIONS,
    RECOMMENDATION_PHRASES,
    STATIC_MESSAGE_TRANSLATIONS,
    EXTRA_MESSAGES,
    PHASE3_MESSAGES,
)


def _merge_translation_tables():
    merged = {}
    for table in _ALL_TRANSLATION_TABLES:
        for key, mapping in table.items():
            entry = merged.setdefault(str(key), {})
            for language in ("en", "te", "hi"):
                value = mapping.get(language)
                if value:
                    entry[language] = value
    return merged


ALL_MESSAGE_TRANSLATIONS = _merge_translation_tables()
ALL_MESSAGE_TRANSLATIONS_CI = {
    key.lower(): entry for key, entry in ALL_MESSAGE_TRANSLATIONS.items()
}


def _exact_translation(text, language):
    """Return the complete translation for a full string, or None."""
    normalized = normalize_language(language)
    key = str(text or "").strip()
    if not key:
        return None
    mapping = ALL_MESSAGE_TRANSLATIONS.get(key)
    if mapping is None:
        mapping = ALL_MESSAGE_TRANSLATIONS_CI.get(key.lower())
    if mapping:
        value = mapping.get(normalized)
        if value:
            return str(value)
    return None


# Mode-note prefixes emitted by the assistant before recommendation answers.
_NOTE_PREFIX_TRANSLATIONS = {
    "For a general plan,": {
        "te": "సాధారణ ప్రణాళిక కోసం,",
        "hi": "सामान्य योजना के लिए,",
    },
    "For farm planning,": {
        "te": "వ్యవసాయ ప్రణాళిక కోసం,",
        "hi": "कृषि योजना के लिए,",
    },
    "For travel planning,": {
        "te": "ప్రయాణ ప్రణాళిక కోసం,",
        "hi": "यात्रा योजना के लिए,",
    },
    "For commute planning,": {
        "te": "కామ్యూట్ ప్రణాళిక కోసం,",
        "hi": "यात्रा योजना के लिए,",
    },
    "For outdoor activity planning,": {
        "te": "బయటి కార్యకలాపాల ప్రణాళిక కోసం,",
        "hi": "बाहरी गतिविधि योजना के लिए,",
    },
}


def _translate_note_prefixes(text, normalized):
    for source, mapping in _NOTE_PREFIX_TRANSLATIONS.items():
        if str(text or "").startswith(source):
            return mapping[normalized] + str(text)[len(source):]
    return text


def _match_note_prefix(text):
    for source, mapping in _NOTE_PREFIX_TRANSLATIONS.items():
        if str(text or "").startswith(source):
            return {"english": source, "te": mapping["te"], "hi": mapping["hi"]}
    return None


# The ML prediction disclaimers appended to some chat answers.
_PREDICTION_SUFFIX_RE = re.compile(
    r"\s*(?:The separate ML rainfall prediction is (?P<pred>.+?) with "
    r"(?P<prob>[0-9]+(?:\.[0-9]+)?)% probability from the (?P<model>[^;]+?) "
    r"model; it is not an official forecast\.?)\s*$",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

def _condition_value(value, normalized):
    """Translate a single weather-condition phrase."""
    return _apply_phrase_map(str(value or ""), WEATHER_CONDITION_TRANSLATIONS, normalized)


def _translate_severity(value, normalized):
    mapping = SEVERITY_TRANSLATIONS.get(str(value or ""), {}).get(normalized)
    return str(mapping) if mapping else str(value or "")


_WINDOW_TRANSLATIONS = {
    "midday": {"te": "మధ్యాహ్నం", "hi": "दोपहर"},
    "early afternoon": {"te": "మధ్యాహ్నం ప్రారంభం", "hi": "दोपहर की शुरुआत में"},
    "early morning": {"te": "ఉదయాన్నే", "hi": "सुबह जल्दी"},
    "late morning": {"te": "ఉదయం ఆలస్యంగా", "hi": "देर सुबह"},
}

_OUTDOOR_DAY_ADVICE = {
    "Carry an umbrella and have an indoor option": {
        "te": "గొడుగు తీసుకెళ్లి, లోపల ఉండే ప్రత్యామ్నాయం కలిగి ఉండండి",
        "hi": "छाता साथ रखें और घर के अंदर रहने का विकल्प रखें",
    },
    "An umbrella is unlikely to be needed": {
        "te": "గొడుగు అవసరం ఉండే అవకాశం లేదు",
        "hi": "छाते की आवश्यकता होने की संभावना नहीं है",
    },
    "take heat precautions and plan breaks": {
        "te": "వేడి జాగ్రత్తలు తీసుకుని విరామాలు ప్లాన్ చేయండి",
        "hi": "गर्मी से बचाव करें और ब्रेक की योजना बनाएँ",
    },
    "conditions look moderate for outdoor plans": {
        "te": "బయటి ప్రణాళికలకు పరిస్థితులు మితంగా ఉన్నాయి",
        "hi": "बाहरी योजनाओं के लिए स्थितियाँ मध्यम हैं",
    },
}

_DAY_TRANSLATIONS = {"Today": {"te": "నేడు", "hi": "आज"}, "Tomorrow": {"te": "రేపు", "hi": "कल"}}


def _match_structured_patterns(text, normalized):
    """Localize known generated sentence shapes; return None when unmatched."""
    if not text:
        return None
    # Structured answers start with a mode-note prefix in English. Translate
    # the prefix first so every generated sentence is fully localized.
    work = _translate_note_prefixes(text, normalized)

    # --- Current / generic conditions -------------------------------
    current_pattern = re.compile(
        r"(?P<prefix>.+? )?(?:Today in|Current conditions in) (?P<location>[^:]+): "
        r"(?P<condition>[^,]+), (?P<temperature>[^ ]+)°C \(feels like "
        r"(?P<feels_like>[^ ]+)°C\), humidity (?P<humidity>[^%]+)%, "
        r"wind (?P<wind>[^ ]+) km/h, and precipitation (?P<precipitation>[^ ]+) mm\.",
        re.IGNORECASE,
    )
    match = current_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        wcondition = _condition_value(values["condition"], normalized)
        if normalized == "te":
            return (
                f"{values['prefix'] or ''}నేడు {values['location']}లో ప్రస్తుత పరిస్థితులు: "
                f"{wcondition}, {values['temperature']}°C (అనుభూతి {values['feels_like']}°C), "
                f"తేమ {values['humidity']}%, గాలి {values['wind']} km/h, మరియు వర్షపాతం "
                f"{values['precipitation']} mm."
            )
        return (
            f"{values['prefix'] or ''}आज {values['location']} में वर्तमान परिस्थितियाँ: "
            f"{wcondition}, {values['temperature']}°C (महसूस {values['feels_like']}°C), "
            f"नमी {values['humidity']}%, हवा {values['wind']} km/h और वर्षा "
            f"{values['precipitation']} mm है।"
        )

    # --- Tomorrow forecast ------------------------------------------
    tomorrow_pattern = re.compile(
        r"(?P<prefix>.+? )?Tomorrow in (?P<location>[^:]+): (?P<condition>[^,]+), "
        r"temperatures from (?P<minimum>[^ ]+) to (?P<maximum>[^ ]+)°C, "
        r"rain probability (?P<probability>[^%]+)%, and precipitation "
        r"(?P<precipitation>[^ ]+) mm\.",
        re.IGNORECASE,
    )
    match = tomorrow_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        wcondition = _condition_value(values["condition"], normalized)
        if normalized == "te":
            return (
                f"{values['prefix'] or ''}రేపు {values['location']}: {wcondition}, ఉష్ణోగ్రత "
                f"{values['minimum']} నుండి {values['maximum']}°C, వర్షం అవకాశం "
                f"{values['probability']}%, మరియు వర్షపాతం {values['precipitation']} mm."
            )
        return (
            f"{values['prefix'] or ''}कल {values['location']}: {wcondition}, तापमान "
            f"{values['minimum']} से {values['maximum']}°C, बारिश की संभावना "
            f"{values['probability']}% और वर्षा {values['precipitation']} mm है।"
        )

    # --- Rain probability -------------------------------------------
    probability_pattern = re.compile(
        r"(?P<prefix>.+? )?Today[’']s rain probability for (?P<location>.+?) is "
        r"(?P<probability>[^%]+)%\.",
        re.IGNORECASE,
    )
    match = probability_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        if normalized == "te":
            return f"{values['prefix'] or ''}నేడు {values['location']}లో వర్షం పడే అవకాశం {values['probability']}%."
        return f"{values['prefix'] or ''}आज {values['location']} में बारिश की संभावना {values['probability']}% है।"

    # --- ML prediction fragments used inside recommendations --------
    rainfall_fragment = re.fullmatch(
        r"Rainfall \((?P<prob>[0-9]+(?:\.[0-9]+)?)% probability\) is expected\.",
        work,
        re.IGNORECASE,
    )
    if rainfall_fragment:
        value = rainfall_fragment.group("prob")
        if normalized == "te":
            return f"వర్షపాతం ({value}% అవకాశం) ఉండవచ్చు."
        return f"बारिश ({value}% संभावना) होने की संभावना है।"

    heavy_fragment = re.fullmatch(
        r"Heavy rainfall \((?P<prob>[0-9]+(?:\.[0-9]+)?)% probability\) is expected\.",
        work,
        re.IGNORECASE,
    )
    if heavy_fragment:
        value = heavy_fragment.group("prob")
        if normalized == "te":
            return f"భారీ వర్షపాతం ({value}% అవకాశం) ఉండవచ్చు."
        return f"भारी बारिश ({value}% संभावना) होने की संभावना है।"

# --- Today's AI summary ------------------------------------------
    summary_pattern = re.compile(
        r"^Today in (?P<location>.+?)"
        r"(?: will be (?P<state>warm|pleasant|cool) \((?P<temp>[0-9]+(?:\.[0-9]+)?)°C\))?\. "
        r"with (?P<condition>.+?) conditions\. "
        r"(?P<rain>and high likelihood of rain|and possible rain|and low chance of rain|"
        r"with low chance of rain)\. "
        r"(?:(?P<wind>Strong winds are expected|Moderate winds are expected)\. )?"
        r"(?P<rec>Carry rain protection if going outside\.|Use sun protection if going outside\.|"
        r"Wear appropriate layers when going outside\.|"
        r"Conditions are generally suitable for outdoor activities\.)",
        re.IGNORECASE,
    )
    match = summary_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        location = values["location"]
        condition = _condition_value(values["condition"], normalized)
        if normalized == "te":
            day_part = f"నేడు {location}"
            if values["temp"]:
                state = _exact_translation(f"will be {values['state']}", normalized) or values["state"]
                day_part += f" {state} ({values['temp']}°C)"
            rain = _exact_translation(values["rain"], normalized) or ""
            rec = _exact_translation(values["rec"], normalized) or ""
            wind_part = ""
            if values["wind"]:
                wind_part = (_exact_translation(values["wind"], normalized) or "") + ". "
            return f"{day_part}. {condition} పరిస్థితులతో, {rain}. {wind_part}{rec}"
        day_part = f"आज {location}"
        if values["temp"]:
            state = _exact_translation(f"will be {values['state']}", normalized) or values["state"]
            day_part += f" {state} ({values['temp']}°C)"
        rain = _exact_translation(values["rain"], normalized) or ""
        rec = _exact_translation(values["rec"], normalized) or ""
        wind_part = ""
        if values["wind"]:
            wind_part = (_exact_translation(values["wind"], normalized) or "") + "। "
        return f"{day_part} है। {condition} परिस्थितियों के साथ, {rain}। {wind_part}{rec}"

# --- Best time window --------------------------------------------
    best_time_pattern = re.compile(
        r"(?P<prefix>.+? )?Best time for outdoor plans in (?P<location>.+?) is "
        r"(?P<window>[^,]+), when rainfall risk is lower and temperatures are "
        r"more comfortable \((?P<mint>[0-9.]+)°C to (?P<maxt>[0-9.]+)°C, "
        r"(?P<prob>[0-9.]+)% rain chance\)\.",
        re.IGNORECASE,
    )
    match = best_time_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        window = _WINDOW_TRANSLATIONS.get(values["window"], {}).get(normalized, values["window"])
        if normalized == "te":
            return (
                f"{values['prefix'] or ''}బయటి ప్రణాళికలకు {values['location']}లో ఉత్తమ సమయం {window}; "
                f"వర్షపు ప్రమాదం తక్కువగా ఉన్నప్పుడు ఉష్ణోగ్రతలు సౌకర్యవంతంగా ఉంటాయి "
                f"({values['mint']}°C నుండి {values['maxt']}°C, {values['prob']}% వర్షం అవకాశం)."
            )
        return (
            f"{values['prefix'] or ''}{values['location']} में बाहरी योजनाओं के लिए सबसे अच्छा समय "
            f"{window} है; जब बारिश का जोखिम कम हो और तापमान अधिक आरामदायक हो "
            f"({values['mint']}°C से {values['maxt']}°C, {values['prob']}% बारिश की संभावना)।"
        )

    best_time_fallback = re.compile(
        r"(?P<prefix>.+? )?The most comfortable window in (?P<location>.+?) is likely "
        r"late morning, based on the available forecast\.",
        re.IGNORECASE,
    )
    match = best_time_fallback.fullmatch(work)
    if match:
        values = match.groupdict()
        if normalized == "te":
            return f"{values['prefix'] or ''}అందుబాటులో ఉన్న అంచనా ప్రకారం {values['location']}లో మంచి సమయం ఉదయం ఆలస్యంగా ఉండవచ్చు."
        return f"{values['prefix'] or ''}उपलब्ध पूर्वानुमान के अनुसार {values['location']} में सबसे उपयुक्त समय देर सुबह हो सकता है।"

    # --- Disaster risk outlook ---------------------------------------
    risk_pattern = re.compile(
        r"(?P<prefix>.+? )?For (?P<location>.+?), the current rule-based risk outlook is: "
        r"flood (?P<flood>\w+), heatwave (?P<heat>\w+), and heavy rain (?P<rain>\w+)\. "
        r"This is an indication from the available weather readings, not an official "
        r"emergency warning\.",
        re.IGNORECASE,
    )
    match = risk_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        flood = _translate_severity(values["flood"], normalized)
        heat = _translate_severity(values["heat"], normalized)
        rain = _translate_severity(values["rain"], normalized)
        if normalized == "te":
            return (
                f"{values['prefix'] or ''}{values['location']}కి ప్రస్తుత నియమ-ఆధారిత ప్రమాద సూచన: "
                f"వరద {flood}, వడగాలి {heat} మరియు భారీ వర్షం {rain}. ఇది అందుబాటులో ఉన్న "
                f"వాతావరణ కొలతల ఆధారంగా ఇచ్చే సూచన మాత్రమే, అధికారిక అత్యవసర హెచ్చరిక కాదు."
            )
        return (
            f"{values['prefix'] or ''}{values['location']} के लिए वर्तमान नियम-आधारित जोखिम: "
            f"बाढ़ {flood}, लू {heat} और भारी बारिश {rain}। यह उपलब्ध मौसम मापों से मिला "
            f"संकेत है, आधिकारिक आपातकालीन चेतावनी नहीं।"
        )

# --- Rain/outdoor day advice -------------------------------------
    day_advice_pattern = re.compile(
        r"(?P<prefix>.+? )?(?P<day>Today|Tomorrow) in (?P<location>.+?), "
        r"(?P<rain_advice>Carry an umbrella and have an indoor option|"
        r"An umbrella is unlikely to be needed); "
        r"(?P<heat_advice>take heat precautions and plan breaks|"
        r"conditions look moderate for outdoor plans)\. "
        r"Check local official guidance if conditions become severe\.",
        re.IGNORECASE,
    )
    match = day_advice_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        day = _DAY_TRANSLATIONS.get(values["day"], {}).get(normalized, values["day"])
        rain_advice = _OUTDOOR_DAY_ADVICE.get(values["rain_advice"], {}).get(normalized, "")
        heat_advice = _OUTDOOR_DAY_ADVICE.get(values["heat_advice"], {}).get(normalized, "")
        if normalized == "te":
            return (
                f"{values['prefix'] or ''}{day} {values['location']}లో, {rain_advice}; {heat_advice}. "
                f"పరిస్థితులు తీవ్రంగా మారితే స్థానిక అధికారిక సూచనలను చూడండి."
            )
        return (
            f"{values['prefix'] or ''}{day} {values['location']} में, {rain_advice}; {heat_advice}. "
            f"स्थिति गंभीर होने पर स्थानीय आधिकारिक दिशा-निर्देश देखें।"
        )

    # --- Seven-day forecast ------------------------------------------
    forecast_pattern = re.compile(
        r"(?P<prefix>.+? )?Here is the available seven-day forecast for "
        r"(?P<location>.+?): (?P<days>.+)$",
        re.IGNORECASE,
    )
    match = forecast_pattern.fullmatch(work)
    if match:
        values = match.groupdict()
        day_items = []
        for item in str(values["days"]).split("; "):
            item_match = re.fullmatch(
                r"(?P<date>[^:]+): (?P<cond>.+?), (?P<mint>[0-9.]+) to "
                r"(?P<maxt>[0-9.]+)°C, rain (?P<prob>[0-9.]+)%",
                item,
                re.IGNORECASE,
            )
            if not item_match:
                day_items.append(item)
                continue
            parts = item_match.groupdict()
            wcond = _condition_value(parts["cond"], normalized)
            if normalized == "te":
                day_items.append(f"{parts['date']}: {wcond}, {parts['mint']} నుండి {parts['maxt']}°C, వర్షం {parts['prob']}%")
            else:
                day_items.append(f"{parts['date']}: {wcond}, {parts['mint']} से {parts['maxt']}°C, बारिश {parts['prob']}%")
        if normalized == "te":
            return f"{values['prefix'] or ''}{values['location']}కి అందుబాటులో ఉన్న ఏడు రోజుల అంచనా: {'; '.join(day_items)}."
        return f"{values['prefix'] or ''}{values['location']} के लिए उपलब्ध सात-दिन का पूर्वानुमान: {'; '.join(day_items)}।"

# --- ML explanation patterns -------------------------------------
    no_factor_pattern = re.compile(
        r"(?P<prefix>.+? )?The available weather and model inputs are used to estimate "
        r"rainfall for (?P<location>.+?); feature importance details are not available "
        r"for this prediction\.",
        re.IGNORECASE,
    )
    match = no_factor_pattern.fullmatch(work)
    if match:
        location = match.group("location")
        if normalized == "te":
            return (
                f"{location} కోసం వర్షపాతాన్ని అంచనా వేయడానికి అందుబాటులో ఉన్న వాతావరణం మరియు "
                f"మోడల్ ఇన్‌పుట్‌లను ఉపయోగిస్తారు; ఈ అంచనాకు ఫీచర్ ప్రాముఖ్యత వివరాలు అందుబాటులో లేవు."
            )
        return (
            f"{location} के लिए बारिश का अनुमान लगाने हेतु उपलब्ध मौसम और मॉडल इनपुट का उपयोग "
            f"किया जाता है; इस अनुमान के लिए फीचर महत्व विवरण उपलब्ध नहीं हैं।"
        )

    factor_pattern = re.compile(
        r"(?P<prefix>.+? )?The ML rainfall estimate for (?P<location>.+?) is based on the "
        r"supplied weather inputs\. The model's leading available factors are "
        r"(?P<factors>.+)\.",
        re.IGNORECASE,
    )
    match = factor_pattern.fullmatch(work)
    if match:
        location = match.group("location")
        factors = _apply_phrase_map(match.group("factors"), COMMON_TRANSLATIONS, normalized)
        if normalized == "te":
            return (
                f"{location} కోసం ఎంఎల్ వర్షపాతం అంచనా అందించిన వాతావరణ ఇన్‌పుట్‌లపై ఆధారపడి ఉంటుంది. "
                f"మోడల్‌లో అందుబాటులో ఉన్న ప్రధాన కారకాలు {factors}."
            )
        return (
            f"{location} के लिए एमएल बारिश का अनुमान दिए गए मौसम इनपुट पर आधारित है। "
            f"मॉडल के प्रमुख उपलब्ध कारक हैं: {factors}।"
        )

    # --- Simple "not available" answers ------------------------------
    not_available_patterns = (
        (r"Rain probability is not available for (?P<location>.+?) in the current forecast\.",
         "{loc}కి ప్రస్తుత అంచనాలో వర్షం అవకాశం అందుబాటులో లేదు.",
         "{loc} के लिए वर्तमान पूर्वानुमान में बारिश की संभावना उपलब्ध नहीं है।"),
        (r"Tomorrow[’']s forecast is not available for (?P<location>.+?)\.",
         "{loc}కి రేపటి అంచనా అందుబాటులో లేదు.",
         "{loc} के लिए कल का पूर्वानुमान उपलब्ध नहीं है।"),
        (r"The forecast is not available for (?P<location>.+?)\.",
         "{loc}కి వాతావరణ అంచనా అందుబాటులో లేదు.",
         "{loc} के लिए पूर्वानुमान उपलब्ध नहीं है।"),
        (r"I cannot assess outdoor conditions for (?P<location>.+?) because the forecast is unavailable\.",
         "{loc}కి అంచనా అందుబాటులో లేనందున బయటి పరిస్థితులను అంచనా వేయలేను.",
         "{loc} के लिए पूर्वानुमान उपलब्ध न होने के कारण मैं बाहरी स्थितियों का आकलन नहीं कर सकता।"),
    )
    for pattern, te_template, hi_template in not_available_patterns:
        match = re.compile(r"(?P<prefix>.+? )?" + pattern, re.IGNORECASE).fullmatch(work)
        if match:
            location = match.group("location")
            if normalized == "te":
                return f"{match.group('prefix') or ''}{te_template.format(loc=location)}"
            return f"{match.group('prefix') or ''}{hi_template.format(loc=location)}"

    return None

def _translate_prediction_suffix(suffix, normalized):
    match = _PREDICTION_SUFFIX_RE.search(suffix)
    if not match:
        return suffix
    prediction = _exact_translation(match.group("pred"), normalized) or match.group("pred")
    probability = match.group("prob")
    model = match.group("model")
    if normalized == "te":
        return f"వేరే ఎంఎల్ వర్షపాత అంచనా {prediction} మరియు {probability}% సంభావ్యతతో {model} మోడల్ నుండి; ఇది అధికారిక అంచనా కాదు."
    return f"{model} मॉडल से {probability}% संभावना के साथ अलग एमएल वर्षा अनुमान {prediction}; यह आधिकारिक पूर्वानुमान नहीं है।"


def _extract_prediction_suffix(text):
    match = _PREDICTION_SUFFIX_RE.search(str(text or ""))
    if not match or match.start() == 0:
        return text, None
    return str(text)[: match.start()].strip(), str(match.group(0)).strip()


def _translate_known_sentences(text, normalized):
    """Localize a message only when every sentence (or sentence range that
    forms a complete translation key) translates completely."""
    sentences = [
        piece.strip()
        for piece in _SENTENCE_SPLIT_RE.split(str(text or "").strip())
        if piece.strip()
    ]
    if not sentences:
        return None

    if len(sentences) == 1:
        exact = _exact_translation(sentences[0], normalized)
        if exact is not None:
            return exact
        structured = _match_structured_patterns(sentences[0], normalized)
        return str(structured) if structured is not None else None

    translated = []
    index = 0
    while index < len(sentences):
        matched = None
        # Prefer the longest run of consecutive sentences that matches a
        # complete translation key (multi-sentence keys must stay intact).
        for end in range(len(sentences), index, -1):
            candidate = " ".join(sentences[index:end])
            exact = _exact_translation(candidate, normalized)
            if exact is not None:
                matched = exact
                index = end
                break
        if matched is None:
            structured = _match_structured_patterns(sentences[index], normalized)
            if structured is None:
                return None
            matched = str(structured)
            index += 1
        translated.append(matched)
    return " ".join(translated)


def _warn_missing_translation(text, normalized):
    key = (normalized, str(text))
    if key in _logged_missing:
        return
    _logged_missing.add(key)
    _logger.warning("Missing %s translation for text: %r", normalized, text)


def _localize_core(text, normalized):
    """Localize a single generated message; return None if not fully localizable."""
    exact = _exact_translation(text, normalized)
    if exact is not None:
        return exact

    structured = _match_structured_patterns(text, normalized)
    if structured is not None:
        return str(structured)

    note = _match_note_prefix(text)
    if note is not None:
        body = str(text)[len(note["english"]):].strip()
        body_localized = _translate_known_sentences(body, normalized)
        if body_localized is not None and body_localized != body:
            return f"{note[normalized]} {body_localized}"
        return None

    return _translate_known_sentences(text, normalized)


def _localize_dynamic(text, normalized):
    """Phase 8 pipeline: exact -> templates -> sentence-level -> English fallback."""
    original = str(text or "").strip()
    if not original or normalized == DEFAULT_LANGUAGE:
        return original

    base, suffix = _extract_prediction_suffix(original)
    if suffix:
        base_localized = _localize_core(base, normalized)
        if base_localized is not None and base_localized != base:
            return f"{base_localized} {_translate_prediction_suffix(suffix, normalized)}"
        return original

    localized = _localize_core(original, normalized)
    if localized is not None and localized != original:
        return str(localized)
    
def normalize_language(language):
    """Normalize the selected language to the current supported set or English fallback."""
    if language is None:
        return DEFAULT_LANGUAGE
    requested = str(language).strip().lower()
    normalized = LANGUAGE_ALIASES.get(requested, DEFAULT_LANGUAGE)
    return normalized if normalized in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_ui_text(language, key, default=None):
    """Return translated UI text for a given language key."""
    normalized = normalize_language(language)
    value = UI_TEXT.get(normalized, {}).get(key)
    if value is not None:
        return value
    if default is not None:
        return default
    return UI_TEXT[DEFAULT_LANGUAGE].get(key, key)


def _apply_phrase_map(text, phrase_map, language):
    """Replace English phrases in a generated string with the selected-language version."""
    if text is None:
        return ""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE:
        return text

    translated = text
    for phrase, mapping in sorted(phrase_map.items(), key=lambda item: len(item[0]), reverse=True):
        replacement = mapping.get(normalized)
        if replacement:
            pattern = re.escape(phrase)
            if phrase[:1].isalnum() and phrase[-1:].isalnum():
                pattern = rf"(?<![A-Za-z-]){pattern}(?![A-Za-z-])"
            translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
    return translated


def _translate_dynamic_sentence(text, language):
    """Translate known generated sentence shapes without altering dynamic values."""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE or not text:
        return text

    scenario_rain = re.fullmatch(r"rainfall probability becomes ([0-9]+)%", text, re.IGNORECASE)
    if scenario_rain:
        value = scenario_rain.group(1)
        return f"వర్షం అవకాశం {value}%కి పెరిగితే" if normalized == "te" else f"अगर बारिश की संभावना {value}% हो जाए"
    scenario_temperature = re.fullmatch(r"temperature reaches ([0-9]+)°C", text, re.IGNORECASE)
    if scenario_temperature:
        value = scenario_temperature.group(1)
        return f"ఉష్ణోగ్రత {value}°Cకి చేరితే" if normalized == "te" else f"अगर तापमान {value}°C तक पहुँच जाए"

    rainfall_recommendation = re.compile(
        r"Rainfall \((?P<probability>[0-9]+(?:\.[0-9]+)?)% probability\) is expected\. Monitor crop conditions\.",
        re.IGNORECASE,
    )
    def translate_rainfall_recommendation(match):
        probability = match.group("probability")
        if normalized == "te":
            return f"వర్షపాతం ({probability}% అవకాశం) ఉండవచ్చు. పంట పరిస్థితులను పర్యవేక్షించండి."
        return f"बारिश ({probability}% संभावना) होने की संभावना है। फसल की स्थिति पर नज़र रखें।"

    translated_rainfall = rainfall_recommendation.sub(translate_rainfall_recommendation, text)
    if translated_rainfall != text:
        text = translated_rainfall

    mode_notes = {
        "For a general plan,": {"te": "సాధారణ ప్రణాళిక కోసం,", "hi": "सामान्य योजना के लिए,"},
        "For farm planning,": {"te": "వ్యవసాయ ప్రణాళిక కోసం,", "hi": "कृषि योजना के लिए,"},
        "For travel planning,": {"te": "ప్రయాణ ప్రణాళిక కోసం,", "hi": "यात्रा योजना के लिए,"},
        "For commute planning,": {"te": "కామ్యూట్ ప్రణాళిక కోసం,", "hi": "यात्रा योजना के लिए,"},
        "For outdoor activity planning,": {"te": "బయటి కార్యకలాపాల ప్రణాళిక కోసం,", "hi": "बाहरी गतिविधि योजना के लिए,"},
    }
    translated = text
    for source, mapping in mode_notes.items():
        translated = translated.replace(source, mapping[normalized])

    def condition(value):
        return _apply_phrase_map(value, WEATHER_CONDITION_TRANSLATIONS, normalized)

    current_pattern = re.compile(
        r"(?P<prefix>.+? )?(?:Today in|Current conditions in) (?P<location>[^:]+): (?P<condition>[^,]+), "
        r"(?P<temperature>[^ ]+)°C \(feels like (?P<feels_like>[^ ]+)°C\), humidity (?P<humidity>[^%]+)%, "
        r"wind (?P<wind>[^ ]+) km/h, and precipitation (?P<precipitation>[^ ]+) mm\."
    )
    match = current_pattern.fullmatch(translated)
    if match:
        values = match.groupdict()
        if normalized == "te":
            sentence = (f"{values['prefix'] or ''}నేడు {values['location']}లో ప్రస్తుత పరిస్థితులు: "
                        f"{condition(values['condition'])}, {values['temperature']}°C (అనుభూతి {values['feels_like']}°C), "
                        f"తేమ {values['humidity']}%, గాలి {values['wind']} km/h, మరియు వర్షపాతం {values['precipitation']} mm.")
        else:
            sentence = (f"{values['prefix'] or ''}आज {values['location']} में वर्तमान परिस्थितियाँ: "
                        f"{condition(values['condition'])}, {values['temperature']}°C (महसूस {values['feels_like']}°C), "
                        f"नमी {values['humidity']}%, हवा {values['wind']} km/h और वर्षा {values['precipitation']} mm है।")
        return sentence

    tomorrow_pattern = re.compile(
        r"(?P<prefix>.+? )?Tomorrow in (?P<location>[^:]+): (?P<condition>[^,]+), temperatures from "
        r"(?P<minimum>[^ ]+) to (?P<maximum>[^ ]+)°C, rain probability (?P<probability>[^%]+)%, and precipitation "
        r"(?P<precipitation>[^ ]+) mm\."
    )
    match = tomorrow_pattern.fullmatch(text)
    if match:
        values = match.groupdict()
        translated_condition = condition(values["condition"])
        prefix = values["prefix"] or ""
        for source, mapping in mode_notes.items():
            prefix = prefix.replace(source, mapping[normalized])
        if normalized == "te":
            return (f"{prefix}రేపు {values['location']}: {translated_condition}, ఉష్ణోగ్రత "
                    f"{values['minimum']} నుండి {values['maximum']}°C, వర్షం అవకాశం {values['probability']}%, "
                    f"మరియు వర్షపాతం {values['precipitation']} mm.")
        return (f"{prefix}कल {values['location']}: {translated_condition}, तापमान "
                f"{values['minimum']} से {values['maximum']}°C, बारिश की संभावना {values['probability']}% "
                f"और वर्षा {values['precipitation']} mm है।")

    probability_pattern = re.compile(r"(?P<prefix>.+? )?Today’s rain probability for (?P<location>.+?) is (?P<probability>[^%]+)%\.")
    match = probability_pattern.fullmatch(text)
    if match:
        values = match.groupdict()
        if normalized == "te":
            return f"{values['prefix'] or ''}నేడు {values['location']}లో వర్షం పడే అవకాశం {values['probability']}%."
        return f"{values['prefix'] or ''}आज {values['location']} में बारिश की संभावना {values['probability']}% है।"

    no_factor_pattern = re.compile(
        r"The available weather and model inputs are used to estimate rainfall for (?P<location>.+?); "
        r"feature importance details are not available for this prediction[.]"
    )
    match = no_factor_pattern.fullmatch(text)
    if match:
        location = match.group("location")
        if normalized == "te":
            return f"{location} కోసం వర్షపాతాన్ని అంచనా వేయడానికి అందుబాటులో ఉన్న వాతావరణం మరియు మోడల్ ఇన్‌పుట్‌లను ఉపయోగిస్తారు; ఈ అంచనాకు ఫీచర్ ప్రాముఖ్యత వివరాలు అందుబాటులో లేవు."
        return f"{location} के लिए बारिश का अनुमान लगाने हेतु उपलब्ध मौसम और मॉडल इनपुट का उपयोग किया जाता है; इस अनुमान के लिए फीचर महत्व विवरण उपलब्ध नहीं हैं।"

    factor_pattern = re.compile(
        r"The ML rainfall estimate for (?P<location>.+?) is based on the supplied weather inputs\. "
        r"The model's leading available factors are (?P<factors>.+)\."
    )
    match = factor_pattern.fullmatch(text)
    if match:
        location = match.group("location")
        factors = _apply_phrase_map(match.group("factors"), COMMON_TRANSLATIONS, normalized)
        if normalized == "te":
            return f"{location} కోసం ఎంఎల్ వర్షపాతం అంచనా అందించిన వాతావరణ ఇన్‌పుట్‌లపై ఆధారపడి ఉంటుంది. మోడల్‌లో అందుబాటులో ఉన్న ప్రధాన కారకాలు {factors}."
        return f"{location} के लिए एमएल बारिश का अनुमान दिए गए मौसम इनपुट पर आधारित है। मॉडल के प्रमुख उपलब्ध कारक हैं: {factors}."

    return translated


def translate_text(text, language):
    """Translate any user-facing generated text through the central message layer."""
    if text is None:
        return ""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE:
        return text
    localized = _localize_dynamic(str(text).strip(), normalized)
    if localized and localized != str(text).strip():
        return str(localized)
    _warn_missing_translation(str(text), normalized)
    return text


def translate_alert(alert, language):
    """Translate a WeatherAlert object or dict to the selected language."""
    normalized = normalize_language(language)
    if isinstance(alert, dict):
        alert_type = alert.get("type", "Weather alert")
        severity = alert.get("severity", "Moderate")
        message = alert.get("message", "")
    else:
        alert_type = getattr(alert, "type", "Weather alert")
        severity = getattr(alert, "severity", "Moderate")
        message = getattr(alert, "message", "")

    translated_type = ALERT_TYPE_TRANSLATIONS.get(alert_type, {}).get(normalized, alert_type)
    translated_severity = SEVERITY_TRANSLATIONS.get(severity, {}).get(normalized, severity)
    translated_message = translate_text(message, normalized)
    if normalized == DEFAULT_LANGUAGE:
        translated_message = message
    return {"type": translated_type, "severity": translated_severity, "message": translated_message}


def translate_recommendation(text, language):
    """Translate generated recommendation strings to the requested language."""
    if text is None:
        return ""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE:
        return text
    return translate_text(text, normalized)


def translate_summary(text, language):
    """Translate weather summary strings while preserving steady data values and units."""
    if text is None:
        return ""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE:
        return text
    return translate_text(text, normalized)


def translate_best_time(text, language):
    """Translate best-time forecast guidance."""
    if text is None:
        return ""
    return translate_summary(text, language)


def translate_phase3_sentence(sentence, language):
    """Translate one Phase 3 personalization sentence.

    The Phase 3 tables are keyed by templates such as
    ``"Rain probability today is {value}%."``, while callers work with the
    already-formatted sentence. This resolves a formatted sentence back to its
    template so the existing Telugu / Hindi entries are actually applied.
    Returns the original sentence when no translation exists, which keeps the
    documented English fallback.
    """
    normalized = normalize_language(language)
    text = str(sentence or "").strip()
    if not text or normalized == DEFAULT_LANGUAGE:
        return text
    direct = _exact_translation(text, normalized)
    if direct is not None:
        return str(direct)
    for template, mapping in PHASE3_MESSAGES.items():
        if "{value}" not in template:
            continue
        value = _template_value(template, text)
        if value is None:
            continue
        localized = mapping.get(normalized)
        if localized:
            return str(localized).replace("{value}", value)
    return text


def _template_value(template, text):
    """Return the ``{value}`` that makes ``template`` render as ``text``."""
    prefix, _, suffix = template.partition("{value}")
    if not text.startswith(prefix) or not text.endswith(suffix):
        return None
    return text[len(prefix) : len(text) - len(suffix)] if suffix else text[len(prefix) :]


def translate_answer_text(text, language):
    """Translate assistant answer snippets to a supported language."""
    if text is None:
        return ""
    normalized = normalize_language(language)
    if normalized == DEFAULT_LANGUAGE:
        return text
    return translate_text(text, normalized)
