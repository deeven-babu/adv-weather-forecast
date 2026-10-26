/* Phase 4 historical analytics charts.
 *
 * Reads the validated payload from /api/analytics/all and renders it with
 * Chart.js. Everything degrades gracefully:
 *   - if Chart.js is unavailable (CDN blocked) a text fallback is shown
 *   - if a section has no data an empty-state message replaces the canvas
 *   - a failed fetch shows an error state instead of stale numbers
 *
 * It never invents values: every number comes from the server response.
 */
(function () {
    'use strict';

    // Two modes share this file:
    //   - the full analytics page, which has [data-analytics-root]
    //   - the dashboard preview card, which has [data-analytics-preview]
    var root = document.querySelector('[data-analytics-root]');
    var preview = document.querySelector('[data-analytics-preview]');
    var scope = root || preview;
    if (!scope) {
        return;
    }

    var endpoint = (root && root.getAttribute('data-endpoint')) || '/api/analytics/all';
    var labels = {};
    try {
        labels = JSON.parse((root && root.getAttribute('data-labels')) || '{}');
    } catch (error) {
        labels = {};
    }

    var stateBox = root ? root.querySelector('[data-analytics-state]') : null;
    var statusText = root ? root.querySelector('[data-analytics-status]') : null;
    var updatedText = root ? root.querySelector('[data-analytics-updated]') : null;
    var charts = {};

    // Chart colours follow the light theme tokens used by style.css.
    var PALETTE = ['#1d91d6', '#0a5ea7', '#7ee7d9', '#ffbf69', '#ff6a7d', '#a06cd5'];
    var LEVEL_COLORS = { Low: '#7adbb3', Moderate: '#ffbf69', High: '#ff8d5e', Critical: '#ff6a7d' };
    var AXIS_COLOR = '#5e7284';
    var GRID_COLOR = 'rgba(18, 59, 88, 0.10)';
    var LEGEND_COLOR = '#17324b';

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function setState(visible, message) {
        if (stateBox) {
            stateBox.hidden = !visible;
        }
        if (statusText && message) {
            statusText.textContent = message;
        }
    }

    function emptyNotice(canvas, message) {
        if (!canvas) {
            return;
        }
        var holder = canvas.parentNode;
        if (!holder || holder.querySelector('.chart-empty')) {
            return;
        }
        canvas.hidden = true;
        var notice = document.createElement('p');
        notice.className = 'chart-empty data-note';
        notice.textContent = message || labels.noData || 'No data for this period.';
        holder.appendChild(notice);
    }

    function clearNotice(canvas) {
        var holder = canvas.parentNode;
        var notice = holder && holder.querySelector('.chart-empty');
        if (notice) {
            notice.remove();
        }
        canvas.hidden = false;
    }

    function hasChartJs() {
        return typeof window.Chart !== 'undefined';
    }

    function render(selector, config) {
        var canvas = scope.querySelector('[data-chart="' + selector + '"]');
        if (!canvas) {
            return;
        }
        if (!hasChartJs()) {
            emptyNotice(canvas, 'Chart library unavailable.');
            return;
        }
        clearNotice(canvas);
        if (charts[selector]) {
            charts[selector].destroy();
        }
        charts[selector] = new window.Chart(canvas.getContext('2d'), config);
    }

    function baseOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: prefersReducedMotion() ? false : { duration: 400 },
            plugins: { legend: { labels: { color: LEGEND_COLOR, boxWidth: 12 } } },
            scales: {
                x: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR } },
                y: { ticks: { color: AXIS_COLOR }, grid: { color: GRID_COLOR }, beginAtZero: true }
            }
        };
    }

    function doughnut(rows, colors) {
        return {
            type: 'doughnut',
            data: {
                labels: rows.map(function (row) { return row.label; }),
                datasets: [{
                    data: rows.map(function (row) { return row.count; }),
                    backgroundColor: colors || PALETTE,
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: prefersReducedMotion() ? false : { duration: 400 },
                plugins: { legend: { position: 'bottom', labels: { color: LEGEND_COLOR, boxWidth: 12 } } }
            }
        };
    }

    function lineChart(rows, field, label, color) {
        return {
            type: 'line',
            data: {
                labels: rows.map(function (row) { return row.date; }),
                datasets: [{
                    label: label,
                    data: rows.map(function (row) { return row[field]; }),
                    borderColor: color,
                    backgroundColor: color + '33',
                    tension: 0.35,
                    spanGaps: true,
                    fill: true,
                    pointRadius: 2
                }]
            },
            options: baseOptions()
        };
    }

    function barChart(rows, field, label, color) {
        return {
            type: 'bar',
            data: {
                labels: rows.map(function (row) { return row.date; }),
                datasets: [{
                    label: label,
                    data: rows.map(function (row) { return row[field]; }),
                    backgroundColor: color + 'cc',
                    borderRadius: 4
                }]
            },
            options: baseOptions()
        };
    }

    function fillSummary(summary) {
        var totals = (summary && summary.totals) || {};
        ['weather_records', 'predictions', 'risk_assessments', 'alerts', 'unread_alerts', 'high_risk_events']
            .forEach(function (key) {
                var node = root.querySelector('[data-stat="' + key + '"]');
                if (node) {
                    node.textContent = (typeof totals[key] === 'number') ? totals[key] : '\u2014';
                }
            });
    }

    function levelRows(levels) {
        return (levels || []).map(function (row) {
            return { label: row.label, count: row.count };
        });
    }

    function levelColors(levels) {
        return (levels || []).map(function (row) {
            return LEVEL_COLORS[row.label] || '#64748b';
        });
    }

    function renderAll(payload) {
        var weather = payload.weather || {};
        var predictions = payload.predictions || {};
        var risk = payload.risk || {};
        var alerts = payload.alerts || {};

        fillSummary(payload.summary);

        // 1. Open-Meteo observed conditions
        var timeline = weather.timeline || [];
        if (timeline.length) {
            render('weather-temperature', lineChart(timeline, 'temperature', labels.temperature || 'Temperature', '#38bdf8'));
            render('weather-humidity', lineChart(timeline, 'humidity', labels.humidity || 'Humidity', '#a78bfa'));
            render('weather-wind', lineChart(timeline, 'wind_speed', labels.wind || 'Wind', '#34d399'));
        } else {
            emptyNotice(root.querySelector('[data-chart="weather-temperature"]'));
            emptyNotice(root.querySelector('[data-chart="weather-humidity"]'));
            emptyNotice(root.querySelector('[data-chart="weather-wind"]'));
        }
        var conditions = weather.conditions || [];
        if (conditions.length) {
            render('weather-conditions', doughnut(conditions));
        } else {
            emptyNotice(root.querySelector('[data-chart="weather-conditions"]'));
        }

        // 2. ML rainfall prediction (trained model, not the forecast)
        var distribution = predictions.distribution || {};
        var rainCount = distribution.rain_expected || 0;
        var dryCount = distribution.no_rain_expected || 0;
        if (rainCount + dryCount > 0) {
            render('ml-distribution', doughnut([
                { label: 'Rain expected', count: rainCount },
                { label: 'No rain expected', count: dryCount }
            ], ['#38bdf8', '#64748b']));
        } else {
            emptyNotice(root.querySelector('[data-chart="ml-distribution"]'));
        }
        if (predictions.has_data) {
            var bands = (predictions.probability_bands || []).map(function (row) {
                return { date: row.label, count: row.count };
            });
            render('ml-bands', barChart(bands, 'count', labels.rainProbability || 'Predictions', '#a78bfa'));
        } else {
            emptyNotice(root.querySelector('[data-chart="ml-bands"]'));
        }
        var mlTimeline = predictions.timeline || [];
        if (mlTimeline.length) {
            render('ml-timeline', lineChart(mlTimeline, 'probability_percent', labels.rainProbability || 'Rain probability', '#38bdf8'));
        } else {
            emptyNotice(root.querySelector('[data-chart="ml-timeline"]'));
        }

        // 3. Rule-based disaster risk (not machine learning)
        var categories = risk.categories || {};
        ['Flood', 'Heatwave', 'Heavy rain'].forEach(function (name) {
            var selector = 'risk-' + name.replace(/ /g, '-');
            var category = categories[name];
            var canvas = root.querySelector('[data-chart="' + selector + '"]');
            if (category && category.total > 0) {
                var rows = levelRows(category.levels);
                render(selector, doughnut(rows, levelColors(category.levels)));
            } else if (canvas) {
                emptyNotice(canvas);
            }
        });
        if (risk.has_data) {
            render('risk-overall', doughnut(levelRows(risk.overall_levels), levelColors(risk.overall_levels)));
        } else {
            emptyNotice(root.querySelector('[data-chart="risk-overall"]'));
        }

        // 4. Alerts
        var byType = alerts.by_type || [];
        if (byType.length) {
            render('alerts-type', doughnut(byType));
        } else {
            emptyNotice(root.querySelector('[data-chart="alerts-type"]'));
        }
        var bySeverity = alerts.by_severity || [];
        if (bySeverity.length) {
            render('alerts-severity', doughnut(bySeverity, ['#34d399', '#fbbf24', '#fb923c', '#ef4444']));
        } else {
            emptyNotice(root.querySelector('[data-chart="alerts-severity"]'));
        }
        var readState = alerts.read_state || {};
        if ((readState.read || 0) + (readState.unread || 0) > 0) {
            render('alerts-read', doughnut([
                { label: 'Read', count: readState.read || 0 },
                { label: 'Unread', count: readState.unread || 0 }
            ], ['#64748b', '#38bdf8']));
        } else {
            emptyNotice(root.querySelector('[data-chart="alerts-read"]'));
        }
        var alertTimeline = alerts.timeline || [];
        if (alertTimeline.length) {
            render('alerts-timeline', barChart(alertTimeline, 'alerts', labels.alerts || 'Alerts', '#fb7185'));
        } else {
            emptyNotice(root.querySelector('[data-chart="alerts-timeline"]'));
        }
    }

    function failAll(message) {
        setState(false, message);
        var canvases = scope.querySelectorAll('.chart-holder canvas');
        for (var index = 0; index < canvases.length; index += 1) {
            emptyNotice(canvases[index], message);
        }
    }

    /* The dashboard preview shows the counters plus two small real charts. */
    function loadPreview() {
        scope.setAttribute('data-analytics-preview-state', 'loading');
        return fetch('/api/analytics/all', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin'
        })
            .then(function (response) {
                if (response.status === 401) {
                    return null;
                }
                if (!response.ok) {
                    throw new Error('failed');
                }
                return response.json();
            })
            .then(function (payload) {
                if (!payload) {
                    scope.setAttribute('data-analytics-preview-state', 'anonymous');
                    return;
                }
                fillSummary(payload.summary);
                renderPreviewCharts(payload);
                scope.setAttribute('data-analytics-preview-state', 'ready');
            })
            .catch(function () {
                scope.setAttribute('data-analytics-preview-state', 'error');
                showPreviewEmpty(labels.failed);
            });
    }

    function showPreviewEmpty(message) {
        scope.querySelectorAll('.chart-holder canvas').forEach(function (canvas) {
            emptyNotice(canvas, message);
        });
    }

    function renderPreviewCharts(payload) {
        var risk = (payload && payload.risk) || {};
        var alerts = (payload && payload.alerts) || {};

        var levels = risk.overall_levels || [];
        var levelTotal = levels.reduce(function (total, row) { return total + (row.count || 0); }, 0);
        if (levelTotal > 0) {
            render('preview-risk', doughnut(levels, levelColors(levels)));
        } else {
            emptyNotice(scope.querySelector('[data-chart="preview-risk"]'));
        }

        var severities = alerts.by_severity || [];
        if (severities.length) {
            render('preview-alerts', doughnut(severities, ['#7adbb3', '#ffbf69', '#ff8d5e', '#ff6a7d']));
        } else {
            emptyNotice(scope.querySelector('[data-chart="preview-alerts"]'));
        }
    }

    function load(days) {
        setState(true, labels.loading);
        var url = endpoint + '?days=' + encodeURIComponent(days);
        return fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
            .then(function (response) {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) {
                    throw new Error('Request failed');
                }
                return response.json();
            })
            .then(function (payload) {
                if (!payload) {
                    return;
                }
                renderAll(payload);
                setState(false);
                if (updatedText) {
                    var generated = (payload.summary && payload.summary.generated_at) || '';
                    updatedText.textContent = (labels.updated || 'Last updated') + ': ' + (generated || '\u2014');
                }
            })
            .catch(function () {
                failAll(labels.failed || 'Analytics could not be loaded.');
            });
    }

    if (root) {
        var rangeButtons = root.querySelectorAll('[data-range]');
        for (var buttonIndex = 0; buttonIndex < rangeButtons.length; buttonIndex += 1) {
            rangeButtons[buttonIndex].addEventListener('click', function (event) {
                for (var other = 0; other < rangeButtons.length; other += 1) {
                    rangeButtons[other].classList.remove('active');
                }
                event.currentTarget.classList.add('active');
                load(event.currentTarget.getAttribute('data-range'));
            });
        }
        load(root.getAttribute('data-days') || 30);
    } else if (preview) {
        // Dashboard preview card: summary counters only.
        loadPreview();
    }
})();
