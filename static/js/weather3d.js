/* Phase 4: live weather dashboard updates + 3D weather/disaster scene.
 *
 * Two independent responsibilities:
 *   1. LiveWeather polls /api/live/weather and updates the existing dashboard
 *      widgets in place, so the page never needs a full reload.
 *   2. WeatherScene renders a Three.js scene whose state is derived from the
 *      real payload (weather condition + rule-based risk), never hard-coded.
 *
 * Degradation rules:
 *   - No WebGL  -> the 3D panel is replaced by a static, informative fallback
 *   - No Three.js from the CDN -> same fallback, the rest of the page works
 *   - The API fails -> the last good values stay visible with an error notice
 *
 * Only one request is made per refresh interval, and the interval is generous
 * so Open-Meteo is never hammered.
 */
(function (window, document) {
    'use strict';

    var RISK_ORDER = { Low: 1, Moderate: 2, High: 3, Critical: 4 };
    var DEFAULT_INTERVAL_MS = 5 * 60 * 1000;

    function clamp(value, minimum, maximum) {
        var number = Number(value);
        if (!isFinite(number)) {
            return minimum;
        }
        return Math.max(minimum, Math.min(maximum, number));
    }

    function riskRank(level) {
        return RISK_ORDER[String(level || 'Low')] || 1;
    }

    function highestRisk(risk) {
        var levels = risk || {};
        return ['flood', 'heatwave', 'rain'].reduce(function (best, key) {
            return riskRank(levels[key]) > riskRank(best) ? levels[key] : best;
        }, 'Low');
    }

    /* ---- State derivation: pure function of the server payload ---------- */

    function deriveSceneState(payload) {
        var current = (payload && payload.current) || {};
        var risk = (payload && payload.risk) || {};
        var forecast = (payload && payload.forecast) || [];
        var today = forecast[0] || {};
        var prediction = payload && payload.rain_prediction;

        var condition = String(current.condition || '').toLowerCase();
        var rainProbability = Number(
            prediction && prediction.probability_percent !== undefined
                ? prediction.probability_percent
                : (today.rain_probability !== undefined ? today.rain_probability : 0)
        );
        rainProbability = clamp(rainProbability, 0, 100);
        var temperature = Number(current.temperature);
        var wind = Number(current.wind_speed);
        var flood = String(risk.flood || 'Low');

        var mode = 'clear';
        if (/thunder|storm/.test(condition)) {
            mode = 'storm';
        } else if (/rain|shower|drizzle/.test(condition) || rainProbability >= 60 || riskRank(risk.rain) >= 3) {
            mode = 'rain';
        } else if (isFinite(temperature) && temperature >= 33 && riskRank(risk.heatwave) >= 2) {
            mode = 'heat';
        } else if (/cloud|fog|mist|haze|overcast/.test(condition)) {
            mode = 'cloudy';
        }

        // Rain particle density follows the real rain signal, not a constant.
        var intensity = rainProbability / 100;
        if (riskRank(risk.rain) >= 3) {
            intensity = Math.max(intensity, 0.75);
        } else if (riskRank(risk.rain) === 2) {
            intensity = Math.max(intensity, 0.45);
        }

        return {
            mode: mode,
            intensity: clamp(intensity, 0, 1),
            rainProbability: rainProbability,
            temperature: isFinite(temperature) ? temperature : null,
            wind: isFinite(wind) ? wind : 0,
            // Water height rises with the flood risk level (Low -> Critical).
            floodLevel: flood,
            floodHeight: { Low: 0.02, Moderate: 0.12, High: 0.24, Critical: 0.36 }[flood] || 0.02,
            heatLevel: riskRank(risk.heatwave),
            rainRisk: String(risk.rain || 'Low'),
            condition: current.condition || '',
            sources: (payload && payload.sources) || {}
        };
    }

    /* ---- WebGL / library detection ------------------------------------- */

    function hasWebGL() {
        try {
            var canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext &&
                (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch (error) {
            return false;
        }
    }

    function showFallback(container, reason) {
        if (!container) {
            return;
        }
        container.classList.add('scene-fallback');
        if (container.querySelector('[data-scene-fallback]')) {
            return;
        }
        var note = document.createElement('div');
        note.className = 'scene-fallback-note';
        note.setAttribute('data-scene-fallback', 'true');
        note.setAttribute('role', 'status');
        note.textContent = reason;
        container.appendChild(note);
    }

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    /* ---- 3D scene ------------------------------------------------------ */

    function WeatherScene(container) {
        this.container = container;
        this.state = null;
        this.frame = null;
        this.clock = 0;
        this.disposed = false;
        this.reduced = prefersReducedMotion();
        // Particle counts are deliberately small so low-end devices stay smooth.
        this.maxDrops = 420;
        this.renderer = null;
        this.ok = false;

        if (!window.THREE) {
            showFallback(container, '3D library unavailable. Live weather data is still shown below.');
            return;
        }
        if (!hasWebGL()) {
            showFallback(container, 'WebGL is not available. Live weather data is still shown below.');
            return;
        }
        try {
            this.init();
            this.ok = true;
        } catch (error) {
            showFallback(container, '3D could not start. Live weather data is still shown below.');
        }
    }

    WeatherScene.prototype.init = function () {
        var THREE = window.THREE;
        var width = this.container.clientWidth || 640;
        var height = this.container.clientHeight || 260;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(52, width / height, 0.1, 200);
        this.camera.position.set(0, 3.2, 11);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
        this.renderer.setSize(width, height);
        this.renderer.domElement.setAttribute('aria-hidden', 'true');
        this.container.appendChild(this.renderer.domElement);

        this.scene.add(new THREE.AmbientLight(0x94a3b8, 0.75));
        var key = new THREE.DirectionalLight(0xffffff, 0.9);
        key.position.set(5, 8, 6);
        this.scene.add(key);

        this.buildBackdrop();
        this.buildSun();
        this.buildClouds();
        this.buildRain();
        this.buildWater();
        this.buildRiskRings();

        this.handleResize = this.resize.bind(this);
        window.addEventListener('resize', this.handleResize);
        this.animate();
    };

    WeatherScene.prototype.buildBackdrop = function () {
        var THREE = window.THREE;
        this.skyMaterial = new THREE.MeshBasicMaterial({
            color: 0x0b1226, transparent: true, opacity: 0.85, side: THREE.BackSide
        });
        this.sky = new THREE.Mesh(new THREE.SphereGeometry(70, 24, 16), this.skyMaterial);
        this.scene.add(this.sky);
    };

    WeatherScene.prototype.buildSun = function () {
        var THREE = window.THREE;
        this.sunMaterial = new THREE.MeshBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.9 });
        this.sun = new THREE.Mesh(new THREE.SphereGeometry(1.1, 20, 14), this.sunMaterial);
        this.sun.position.set(-6.5, 5.5, -4);
        this.scene.add(this.sun);
    };

    WeatherScene.prototype.buildClouds = function () {
        var THREE = window.THREE;
        this.clouds = new THREE.Group();
        // One shared geometry and material keeps the draw cost low.
        var geometry = new THREE.SphereGeometry(1, 14, 10);
        this.cloudMaterial = new THREE.MeshStandardMaterial({
            color: 0x94a3b8, roughness: 1, metalness: 0, transparent: true, opacity: 0.85
        });
        for (var index = 0; index < 9; index += 1) {
            var cloud = new THREE.Mesh(geometry, this.cloudMaterial);
            cloud.position.set(
                (index % 3) * 3.4 - 3.4,
                4.2 + (index % 2) * 0.9,
                -2 - Math.floor(index / 3) * 1.7
            );
            cloud.scale.set(1.7 + (index % 3) * 0.4, 0.75, 1.2);
            cloud.userData.speed = 0.12 + (index % 3) * 0.05;
            this.clouds.add(cloud);
        }
        this.scene.add(this.clouds);
    };

    WeatherScene.prototype.buildRain = function () {
        var THREE = window.THREE;
        // A single BufferGeometry of line segments: one draw call for all rain.
        var positions = new Float32Array(this.maxDrops * 6);
        var geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        this.rainMaterial = new THREE.LineBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.55 });
        this.rain = new THREE.LineSegments(geometry, this.rainMaterial);
        this.rain.frustumCulled = false;
        this.rain.visible = false;
        this.rainPositions = positions;
        this.rainSeeds = [];
        for (var index = 0; index < this.maxDrops; index += 1) {
            this.rainSeeds.push({
                x: (Math.random() - 0.5) * 22,
                y: Math.random() * 12,
                z: -6 + Math.random() * 12
            });
        }
        this.scene.add(this.rain);
    };

    WeatherScene.prototype.buildWater = function () {
        var THREE = window.THREE;
        this.waterMaterial = new THREE.MeshStandardMaterial({
            color: 0x1d4ed8, transparent: true, opacity: 0.62, roughness: 0.25, metalness: 0.1
        });
        this.water = new THREE.Mesh(new THREE.BoxGeometry(20, 1, 14), this.waterMaterial);
        this.water.position.set(0, -2.6, 0);
        this.water.visible = false;
        this.scene.add(this.water);
    };

    WeatherScene.prototype.buildRiskRings = function () {
        var THREE = window.THREE;
        this.rings = {};
        var colors = { flood: 0x38bdf8, heatwave: 0xfb923c, rain: 0xa78bfa };
        var xFor = { flood: -4.4, heatwave: 0, rain: 4.4 };
        ['flood', 'heatwave', 'rain'].forEach(function (key) {
            var mesh = new THREE.Mesh(
                new THREE.TorusGeometry(1.5, 0.055, 10, 40),
                new THREE.MeshBasicMaterial({ color: colors[key], transparent: true, opacity: 0.5 })
            );
            mesh.rotation.x = Math.PI / 2;
            mesh.position.set(xFor[key], 1.1, 0.4);
            mesh.userData.base = 1.1;
            this.rings[key] = mesh;
            this.scene.add(mesh);
        }, this);
    };

    /* ---- State application --------------------------------------------- */

    WeatherScene.prototype.apply = function (state) {
        if (!this.ok || !state) {
            return;
        }
        this.state = state;
        var isRain = state.mode === 'rain' || state.mode === 'storm';
        this.rain.visible = isRain;
        this.sun.visible = state.mode === 'clear' || state.mode === 'heat';
        this.sunMaterial.color.setHex(state.mode === 'heat' ? 0xf97316 : 0xfbbf24);
        this.cloudMaterial.opacity = state.mode === 'clear' ? 0.35 : 0.9;
        this.skyMaterial.color.setHex(
            state.mode === 'storm' ? 0x0a0f1f : (state.mode === 'rain' ? 0x101c33 : 0x0b1226)
        );
        // Flood risk controls the water height; Low keeps it almost flat.
        this.water.visible = state.floodLevel !== 'Low';
        this.water.position.y = -2.6 + state.floodHeight;
        this.rings.flood.material.opacity = 0.25 + riskRank(state.floodLevel) * 0.18;
        this.rings.heatwave.material.opacity = 0.25 + state.heatLevel * 0.16;
        this.rings.rain.material.opacity = 0.25 + riskRank(state.rainRisk) * 0.18;
    };

    WeatherScene.prototype.animate = function () {
        var self = this;
        this.frame = window.requestAnimationFrame(function () {
            if (self.disposed) {
                return;
            }
            self.clock += 0.016;
            var state = self.state;

            if (self.rain.visible) {
                self.updateRain();
            }
            self.clouds.children.forEach(function (cloud) {
                cloud.position.x += cloud.userData.speed * 0.01;
                if (cloud.position.x > 6) {
                    cloud.position.x = -6;
                }
            });
            if (state && state.mode === 'heat') {
                // Gentle warm drift rather than a harsh flash.
                self.sun.position.x = -6.5 + Math.sin(self.clock * 0.6) * 0.4;
                self.sunMaterial.opacity = 0.75 + Math.sin(self.clock * 1.2) * 0.12;
            }
            if (!self.reduced) {
                Object.keys(self.rings).forEach(function (key) {
                    var ring = self.rings[key];
                    ring.position.y = ring.userData.base + Math.sin(self.clock * 1.4 + key.length) * 0.12;
                    ring.rotation.z += 0.002;
                });
                // Subtle camera movement keeps the scene alive without distracting.
                self.camera.position.x = Math.sin(self.clock * 0.18) * 0.7;
            }
            self.camera.lookAt(0, 1.4, 0);
            if (self.renderer) {
                self.renderer.render(self.scene, self.camera);
            }
            self.animate();
        });
    };

    WeatherScene.prototype.updateRain = function () {
        var intensity = (this.state && this.state.intensity) || 0;
        var active = Math.floor(this.maxDrops * intensity);
        var speed = 0.55 + intensity * 0.9;
        var positions = this.rainPositions;
        for (var index = 0; index < this.maxDrops; index += 1) {
            var offset = index * 6;
            if (index >= active) {
                // Collapse unused drops so they cost nothing to draw.
                positions[offset] = 0;
                positions[offset + 1] = -50;
                positions[offset + 2] = 0;
                positions[offset + 3] = 0;
                positions[offset + 4] = -50;
                positions[offset + 5] = 0;
                continue;
            }
            var seed = this.rainSeeds[index];
            seed.y -= speed;
            if (seed.y < -2) {
                seed.y = 12;
            }
            positions[offset] = seed.x;
            positions[offset + 1] = seed.y;
            positions[offset + 2] = seed.z;
            positions[offset + 3] = seed.x + 0.12;
            positions[offset + 4] = seed.y - 0.55;
            positions[offset + 5] = seed.z;
        }
        if (this.rain.geometry) {
            this.rain.geometry.attributes.position.needsUpdate = true;
        }
    };

    WeatherScene.prototype.resize = function () {
        if (!this.ok || !this.container) {
            return;
        }
        var width = this.container.clientWidth || 640;
        var height = this.container.clientHeight || 260;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    };

    WeatherScene.prototype.dispose = function () {
        this.disposed = true;
        if (this.frame) {
            window.cancelAnimationFrame(this.frame);
        }
        if (this.handleResize) {
            window.removeEventListener('resize', this.handleResize);
        }
        if (this.renderer) {
            this.renderer.dispose();
        }
    };

    /* ---- Live dashboard updates ----------------------------------------- */

    function setText(selector, value) {
        var node = document.querySelector(selector);
        if (node) {
            node.textContent = (value === null || value === undefined || value === '') ? '\u2014' : value;
        }
    }

    function setLevel(selector, level) {
        var node = document.querySelector(selector);
        if (node) {
            node.textContent = level;
            // The existing 'level-*' classes are preserved so styling and the
            // current tests both keep working.
            node.className = 'level level-' + String(level || 'low').toLowerCase();
        }
    }

    function LiveWeather(options) {
        this.endpoint = options.endpoint;
        this.city = options.city || '';
        this.root = options.root;
        this.intervalMs = options.intervalMs || DEFAULT_INTERVAL_MS;
        this.timer = null;
        this.scene = options.scene || null;
        this.status = options.status || null;
        this.reduced = prefersReducedMotion();
    }

    LiveWeather.prototype.paint = function (payload) {
        var current = payload.current || {};
        var risk = payload.risk || {};
        var location = payload.location || {};

        setText('[data-live="location"]', location.name);
        setText('[data-live="country"]', location.country);
        setText('[data-live="temperature"]',
            current.temperature !== undefined ? current.temperature + '\u00B0C' : null);
        setText('[data-live="feels-like"]',
            current.feels_like !== undefined ? current.feels_like + '\u00B0C' : null);
        setText('[data-live="condition"]', current.condition);
        setText('[data-live="humidity"]', current.humidity !== undefined ? current.humidity + '%' : null);
        setText('[data-live="wind"]', current.wind_speed !== undefined ? current.wind_speed + ' km/h' : null);
        setText('[data-live="precipitation"]',
            current.precipitation !== undefined ? current.precipitation + ' mm' : null);
        setText('[data-live="pressure"]', current.pressure !== undefined ? current.pressure + ' hPa' : null);

        var forecast = payload.forecast || [];
        setText('[data-live="rain-probability"]', (forecast[0] && forecast[0].rain_probability !== undefined)
            ? forecast[0].rain_probability + '%' : null);

        setText('[data-live="risk-flood"]', risk.flood);
        setText('[data-live="risk-heatwave"]', risk.heatwave);
        setText('[data-live="risk-rain"]', risk.rain);
        setLevel('[data-live-level="flood"]', risk.flood);
        setLevel('[data-live-level="heatwave"]', risk.heatwave);
        setLevel('[data-live-level="rain"]', risk.rain);

        var prediction = payload.rain_prediction;
        setText('[data-live="ml-probability"]',
            (prediction && prediction.probability_percent !== undefined) ? prediction.probability_percent + '%' : null);
        setText('[data-live="ml-result"]', prediction ? prediction.prediction : null);
        setText('[data-live="ml-model"]', prediction ? (prediction.model_name || '\u2014') : null);

        setText('[data-live="unread"]', payload.unread_count);
        setText('[data-live="recommendation"]', payload.recommendation);
        setText('[data-live="updated"]', payload.updated_at);
        setText('[data-live="source-weather"]', (payload.sources || {}).weather);
        setText('[data-live="source-ml"]', (payload.sources || {}).rain_prediction);
        setText('[data-live="source-risk"]', (payload.sources || {}).risk);

        if (this.scene) {
            this.scene.apply(deriveSceneState(payload));
        }
        if (this.root) {
            this.root.setAttribute('data-live-state', 'ready');
        }
    };

    LiveWeather.prototype.setStatus = function (message, kind) {
        if (!this.status) {
            return;
        }
        this.status.textContent = message || '';
        this.status.hidden = !message;
        this.status.setAttribute('data-live-status', kind || 'idle');
    };

    LiveWeather.prototype.refresh = function () {
        var self = this;
        if (this.root) {
            this.root.setAttribute('data-live-state', 'updating');
        }
        this.setStatus(this.reduced ? 'Updating' : 'Updating\u2026', 'updating');
        var url = this.endpoint + '?city=' + encodeURIComponent(this.city);
        return fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
            .then(function (response) {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    return response.json().catch(function () {
                        return {};
                    }).then(function (body) {
                        throw new Error(body.error || 'Live update failed.');
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                if (!payload) {
                    return;
                }
                self.paint(payload);
                self.setStatus('', 'idle');
            })
            .catch(function (error) {
                // Keep the last good values on screen and say what went wrong.
                self.setStatus(error && error.message ? error.message : 'Live update failed.', 'error');
                if (self.root) {
                    self.root.setAttribute('data-live-state', 'error');
                }
            });
    };

    LiveWeather.prototype.start = function () {
        var self = this;
        if (this.timer) {
            window.clearInterval(this.timer);
        }
        // Polling pauses on a hidden tab so no request is wasted.
        this.timer = window.setInterval(function () {
            if (document.visibilityState !== 'hidden') {
                self.refresh();
            }
        }, this.intervalMs);
    };

    /* ---- Bootstrap ------------------------------------------------------ */

    function init() {
        var liveRoot = document.querySelector('[data-live-root]');
        if (!liveRoot) {
            return;
        }
        var sceneHolder = liveRoot.querySelector('[data-scene]');
        var scene = sceneHolder ? new WeatherScene(sceneHolder) : null;
        var live = new LiveWeather({
            endpoint: liveRoot.getAttribute('data-live-endpoint') || '/api/live/weather',
            city: liveRoot.getAttribute('data-live-city') || '',
            root: liveRoot,
            scene: scene,
            status: liveRoot.querySelector('[data-live-message]'),
            intervalMs: Number(liveRoot.getAttribute('data-live-interval')) || DEFAULT_INTERVAL_MS
        });
        window.weatherLive = live;
        if (scene) {
            window.weatherScene = scene;
        }
        live.refresh();
        live.start();
    }

    // Exposed so the derivation can be unit-tested and reused elsewhere.
    window.WeatherAI = window.WeatherAI || {};
    window.WeatherAI.deriveSceneState = deriveSceneState;
    window.WeatherAI.riskRank = riskRank;
    window.WeatherAI.highestRisk = highestRisk;
    window.WeatherAI.hasWebGL = hasWebGL;
    window.WeatherAI.WeatherScene = WeatherScene;
    window.WeatherAI.LiveWeather = LiveWeather;
    window.WeatherAI.prefersReducedMotion = prefersReducedMotion;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window, document);
