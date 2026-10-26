
document.addEventListener('DOMContentLoaded', () => {
    const i18n = window.weatherI18n || {};
    const themeToggle = document.querySelector('.theme-toggle');
    const languageSelect = document.querySelector('[data-language-select]');
    const savedTheme = localStorage.getItem('weather-theme');

    if (languageSelect) {
        languageSelect.addEventListener('change', async () => {
            const language = languageSelect.value;
            try {
                const response = await fetch('/api/language', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ language })
                });
                if (!response.ok) {
                    throw new Error(i18n.languageError || 'Unable to update language');
                }
                window.location.reload();
            } catch (error) {
                console.error('Language change failed:', error);
            }
        });
    }

    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
    }

    if (themeToggle) {
        const syncThemeLabel = () => {
            const lightMode = document.body.classList.contains('light-theme');
            themeToggle.textContent = lightMode ? '☾' : '☼';
        };

        syncThemeLabel();

        themeToggle.addEventListener('click', () => {
            const isLightMode = document.body.classList.toggle('light-theme');
            localStorage.setItem('weather-theme', isLightMode ? 'light' : 'dark');
            syncThemeLabel();
        });
    }

    const searchForm = document.querySelector('.weather-search');
    if (searchForm) {
        searchForm.addEventListener('submit', () => {
            searchForm.classList.add('is-loading');
        });
    }

    const assistantForm = document.querySelector('[data-assistant-form]');
    const assistantMessages = document.querySelector('[data-assistant-messages]');
    if (assistantForm && assistantMessages) {
        const questionInput = assistantForm.querySelector('input[name="question"]');
        const cityInput = assistantForm.querySelector('input[name="city"]');
        const clearButton = document.querySelector('[data-clear-assistant]');
        const voiceButton = assistantForm.querySelector('[data-voice-input]');
        const voiceStatus = document.querySelector('[data-voice-status]');
        // Phase 3: resolve the recognition / synthesis language dynamically.
        // A `const` captured once at load goes stale, so the live <select> is
        // the source of truth and the others are ordered fallbacks.
        const VOICE_LOCALES = { en: 'en-US', te: 'te-IN', hi: 'hi-IN' };
        const currentLanguage = () => {
            const select = document.querySelector('[data-language-select]');
            const candidate = (select && select.value)
                || i18n.language
                || (document.documentElement && document.documentElement.lang)
                || 'en';
            return String(candidate).trim().toLowerCase().split(/[-_]/)[0];
        };
        const languageCode = () => VOICE_LOCALES[currentLanguage()] || 'en-US';
        let recognition = null;
        let listening = false;

        const setVoiceStatus = (message) => {
            if (voiceStatus) voiceStatus.textContent = message || '';
        };

        const stopListening = () => {
            if (recognition && listening) recognition.stop();
        };

        if (voiceButton) {
            const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!Recognition) {
                voiceButton.disabled = true;
                voiceButton.title = i18n.voiceUnsupported;
                voiceButton.setAttribute('aria-label', i18n.voiceUnsupported);
            } else {
                recognition = new Recognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;
                recognition.onstart = () => {
                    listening = true;
                    voiceButton.classList.add('is-listening');
                    voiceButton.setAttribute('aria-label', i18n.voiceStop);
                    voiceButton.title = i18n.voiceStop;
                    setVoiceStatus(i18n.voiceListening);
                };
                recognition.onresult = (event) => {
                    // Walk every result, not just index 0, so a transcript is
                    // never dropped. `trim()` is Unicode-safe for Telugu.
                    let transcript = '';
                    for (let i = 0; i < event.results.length; i += 1) {
                        const result = event.results[i];
                        for (let j = 0; j < result.length; j += 1) {
                            if (typeof result[j].transcript === 'string' && result[j].transcript.trim()) {
                                transcript += result[j].transcript;
                            }
                        }
                    }
                    transcript = transcript.trim();
                    if (!transcript) {
                        setVoiceStatus(i18n.voiceNoSpeech);
                        return;
                    }
                    questionInput.value = transcript;
                    setVoiceStatus(i18n.assistantLoading || 'Checking the latest available weather...');
                    // Ask straight away so a spoken question produces an answer
                    // instead of silently waiting for the Send button.
                    assistantForm.requestSubmit
                        ? assistantForm.requestSubmit()
                        : assistantForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                };
                recognition.onerror = (event) => {
                    const message = event.error === 'not-allowed' || event.error === 'service-not-allowed'
                        ? i18n.voiceDenied
                        : event.error === 'no-speech' ? i18n.voiceNoSpeech : i18n.voiceError;
                    setVoiceStatus(message);
                };
                recognition.onend = () => {
                    listening = false;
                    voiceButton.classList.remove('is-listening');
                    voiceButton.setAttribute('aria-label', i18n.voiceStart);
                    voiceButton.title = i18n.voiceStart;
                    if (voiceStatus && voiceStatus.textContent === i18n.voiceListening) setVoiceStatus('');
                };
                voiceButton.addEventListener('click', () => {
                    if (listening) {
                        stopListening();
                        return;
                    }
                    setVoiceStatus(i18n.voiceListening);
                    try {
                        // Re-apply the locale on every start: a single instance is
                        // reused, so this is what keeps the language current.
                        recognition.lang = languageCode();
                        recognition.start();
                    } catch (error) {
                        setVoiceStatus(i18n.voiceError);
                    }
                });
            }
        }
        const addMessage = (message, role) => {
            const item = document.createElement('div');
            item.className = `chat-message chat-message-${role}`;
            item.innerHTML = role === 'assistant'
            ? `<span class="chat-avatar" aria-hidden="true">◌</span><p></p>`
                : '<p></p>';
            item.querySelector('p').textContent = message;
            assistantMessages.appendChild(item);
            assistantMessages.scrollTop = assistantMessages.scrollHeight;
            return item;
        };

        const addSpeakButton = (item) => {
            if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
                setVoiceStatus(i18n.voiceUnavailable);
                return;
            }
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'speak-button';
            button.textContent = '🔊';
            button.setAttribute('aria-label', i18n.voiceRead);
            button.title = i18n.voiceRead;
            button.addEventListener('click', () => {
                if (window.speechSynthesis.speaking) {
                    window.speechSynthesis.cancel();
                    button.setAttribute('aria-label', i18n.voiceRead);
                    button.title = i18n.voiceRead;
                    setVoiceStatus('');
                    return;
                }
                const utterance = new SpeechSynthesisUtterance(item.querySelector('p').textContent);
                utterance.lang = languageCode();
                // Voices load asynchronously in some browsers, so wait briefly.
                const locale = utterance.lang;
                const pickVoice = () => {
                    const voices = window.speechSynthesis.getVoices() || [];
                    const base = locale.slice(0, 2).toLowerCase();
                    return voices.find((voice) => voice.lang && voice.lang.toLowerCase().replace('_', '-').startsWith(base));
                };
                const speak = () => {
                    const matchingVoice = pickVoice();
                    if (matchingVoice) {
                        utterance.voice = matchingVoice;
                    } else {
                        // A missing language voice must never block the reply.
                        // Speak with the browser default while keeping the text.
                        setVoiceStatus(i18n.voiceUnavailable);
                    }
                    window.speechSynthesis.speak(utterance);
                };
                utterance.onstart = () => {
                    button.setAttribute('aria-label', i18n.voiceStopSpeaking);
                    button.title = i18n.voiceStopSpeaking;
                    setVoiceStatus(i18n.voiceSpeaking);
                };
                utterance.onend = utterance.onerror = () => {
                    button.setAttribute('aria-label', i18n.voiceRead);
                    button.title = i18n.voiceRead;
                    setVoiceStatus('');
                };
                const voicesReady = window.speechSynthesis.getVoices() || [];
                if (voicesReady.length > 0) {
                    speak();
                } else {
                    window.speechSynthesis.addEventListener('voiceschanged', speak, { once: true });
                    // Never leave the button dead if the event never fires.
                    setTimeout(speak, 600);
                }
            });
            item.appendChild(button);
        };

        document.querySelectorAll('[data-question]').forEach((button) => {
            button.addEventListener('click', () => {
                questionInput.value = button.dataset.question;
                questionInput.focus();
            });
        });

        if (clearButton) {
            clearButton.addEventListener('click', () => {
                assistantMessages.innerHTML = '';
            });
        }

        assistantForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const question = questionInput.value.trim();
            if (!question) return;
            addMessage(question, 'user');
            questionInput.value = '';
            questionInput.disabled = true;
            assistantForm.querySelector('button').disabled = true;
            const loading = addMessage(i18n.assistantLoading || 'Checking the latest available weather...', 'assistant');
            loading.classList.add('is-loading');
            try {
                const response = await fetch('/api/assistant', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=UTF-8' },
                    body: JSON.stringify({ question, city: cityInput.value })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || i18n.assistantUnavailable || 'The assistant is unavailable right now.');
                loading.querySelector('p').textContent = data.answer;
                addSpeakButton(loading);
                loading.classList.remove('is-loading');
            } catch (error) {
                loading.querySelector('p').textContent = error.message;
                loading.classList.remove('is-loading');
                loading.classList.add('chat-message-error');
            } finally {
                questionInput.disabled = false;
                assistantForm.querySelector('button').disabled = false;
                questionInput.focus();
            }
        });
    }

    const scenarioForm = document.querySelector('[data-scenario-form]');
    const scenarioResult = document.querySelector('[data-scenario-result]');
    if (scenarioForm && scenarioResult) {
        const scenarioCityInput = document.querySelector('[data-assistant-form] input[name="city"]');
        scenarioForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const input = scenarioForm.querySelector('input[name="scenario"]');
            const button = scenarioForm.querySelector('button');
            button.disabled = true;
            scenarioResult.textContent = i18n.scenarioLoading || 'Running simulation...';
            try {
                const response = await fetch('/api/phase9/scenario', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ scenario: input.value, city: scenarioCityInput ? scenarioCityInput.value : '' })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || i18n.scenarioUnavailable || 'Simulation unavailable.');
                scenarioResult.textContent = `${data.result.label} ${data.result.scenario}. ${data.result.impact}`;
            } catch (error) {
                scenarioResult.textContent = error.message;
            } finally {
                button.disabled = false;
            }
        });
    }

    const mapElement = document.querySelector('#weather-map');
    if (mapElement && window.L) {
        const latitude = Number(mapElement.dataset.latitude);
        const longitude = Number(mapElement.dataset.longitude);
        const weather = JSON.parse(mapElement.dataset.weather);
        const mapStatus = document.querySelector('.map-status');
        const map = L.map(mapElement, { scrollWheelZoom: false }).setView([latitude, longitude], 10);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        let marker = L.marker([latitude, longitude]).addTo(map);

        const popupContent = (location, current) => `
            <div class="weather-popup">
                <strong>${location.name}${location.country ? `, ${location.country}` : ''}</strong>
                <span>${Math.round(current.temperature)}°C · ${current.condition}</span>
                <span>${i18n.humidity || 'Humidity'} ${Math.round(current.humidity)}% · ${i18n.wind || 'Wind'} ${Math.round(current.wind_speed)} km/h</span>
            </div>`;

        marker.bindPopup(popupContent(weather.location, { ...weather.current, condition: mapElement.dataset.conditionLabel || weather.current.condition }));

        const selectCoordinates = (lat, lon) => {
            if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
                if (mapStatus) mapStatus.textContent = i18n.invalidMap || 'That map location is not valid. Please try again.';
                return;
            }
            if (mapStatus) mapStatus.textContent = i18n.loadingMap || 'Loading local conditions...';
            map.setView([lat, lon], 10);
            marker.setLatLng([lat, lon]).closePopup();
            const params = new URLSearchParams({ latitude: lat.toFixed(6), longitude: lon.toFixed(6) });
            window.location.assign(`/dashboard?${params.toString()}`);
        };

        map.on('click', (event) => selectCoordinates(event.latlng.lat, event.latlng.lng));

        const useLocationButton = document.querySelector('[data-use-location]');
        if (useLocationButton) {
            useLocationButton.addEventListener('click', () => {
                if (!navigator.geolocation) {
                    if (mapStatus) mapStatus.textContent = i18n.unsupportedLocation || 'Location services are not supported by this browser.';
                    return;
                }
                useLocationButton.disabled = true;
                if (mapStatus) mapStatus.textContent = i18n.requestingLocation || 'Requesting your location...';
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        useLocationButton.disabled = false;
                        selectCoordinates(position.coords.latitude, position.coords.longitude);
                    },
                    (error) => {
                        useLocationButton.disabled = false;
                        if (mapStatus) {
                            mapStatus.textContent = error.code === error.PERMISSION_DENIED
                                ? (i18n.permissionDenied || 'Location permission was denied. You can still select a point on the map.')
                                : (i18n.locationUnavailable || 'Your location could not be determined. Please try again or select a point on the map.');
                        }
                    },
                    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
                );
            });
        }

        window.setTimeout(() => map.invalidateSize(), 100);
    }

    // Phase 7: Mode Selector Functionality
    const modeButtons = document.querySelectorAll('.mode-button');
    if (modeButtons.length > 0) {
        const searchForm = document.querySelector('[data-weather-search]');
        const activeCity = searchForm ? searchForm.dataset.city : '';

        // Refresh the mode-specific recommendation without a full page reload.
        const refreshModeContent = async (mode) => {
            if (!activeCity) return;
            const params = new URLSearchParams({ city: activeCity });
            try {
                // Single source of truth: the intelligence endpoint already combines
                // weather, forecast, ML rainfall prediction, and disaster risk.
                const [intelligence, recommendations] = await Promise.all([
                    fetch(`/api/phase9/intelligence?${params.toString()}`),
                    fetch(`/api/recommendations?${params.toString()}`)
                ]);

                if (intelligence.ok) {
                    const intelligenceData = await intelligence.json();
                    if (intelligenceData.context) {
                        const conditionLabel = document.querySelector('[data-condition-label]');
                        if (conditionLabel && intelligenceData.context.condition) {
                            conditionLabel.textContent = intelligenceData.context.condition;
                        }
                    }
                }

                if (recommendations.ok) {
                    const data = await recommendations.json();
                    if (data.recommendation) {
                        const recommendationText = document.querySelector('[data-recommendation-text]');
                        if (recommendationText) recommendationText.textContent = data.recommendation;
                    }
                    if (data.best_time) {
                        const bestTimeText = document.querySelector('[data-best-time-text]');
                        if (bestTimeText) bestTimeText.textContent = data.best_time;
                    }
                }
            } catch (error) {
                console.error('Mode content refresh error:', error);
            }
        };

        modeButtons.forEach((button) => {
            button.addEventListener('click', async () => {
                const mode = button.dataset.mode;
                try {
                    const response = await fetch('/api/user-mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mode })
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || i18n.modeError || 'Failed to update mode.');

                    // Update active state
                    modeButtons.forEach((btn) => btn.classList.remove('active'));
                    button.classList.add('active');

                    const modeLabel = document.querySelector('[data-mode-label]');
                    if (modeLabel) {
                        const label = button.querySelector('span:not(.mode-icon)');
                        if (label) modeLabel.textContent = label.textContent.trim();
                    }

                    await refreshModeContent(mode);
                } catch (error) {
                    console.error('Mode update error:', error);
                }
            });
        });
    }
});