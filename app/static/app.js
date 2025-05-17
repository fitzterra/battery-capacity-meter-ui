/**
 * Application JS
 **/

let currentChart = null; // Track the current chart instance

// ---- Chart Handling ----
function initChartHandler() {
    document.body.addEventListener('htmx:afterOnLoad', function (evt) {
        const plotter = document.querySelector('.plotter');
        if (!plotter) return;

        const canvas = plotter.querySelector('.battery-plot');
        if (!canvas) return;

        try {
            // Read the raw JSON string that was swapped into the <canvas>
            const json = canvas.textContent.trim();
            const data = JSON.parse(json);

            const title = `${data.cycle} cycle ${data.cycle_num}`;

            // Clear canvas
            canvas.innerHTML = '';

            if (!data.success) {
                canvas.insertAdjacentHTML('afterend', `<p>Error: ${data.msg}</p>`);
                return;
            }

            const voltageData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.bat_v
            }));

            const capacityData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.mah
            }));

            const currentData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.current
            }));

            const ctx = canvas.getContext('2d');

            if (currentChart) {
                currentChart.destroy();
            }

            currentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Battery Voltage (mV)',
                            data: voltageData,
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.2,
                            pointRadius: 0,
                            yAxisID: 'y',
                        },
                        {
                            label: 'Current (mA)',
                            data: currentData,
                            borderColor: 'rgb(255, 206, 86)',
                            tension: 0.2,
                            pointRadius: 0,
                            yAxisID: 'y1',
                        },
                        {
                            label: 'Charge (mAh)',
                            data: capacityData,
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            tension: 0.2,
                            pointRadius: 0,
                            yAxisID: 'y2',
                        },
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                unit: 'second',
                                tooltipFormat: 'HH:mm:ss',
                                displayFormats: {
                                    second: 'HH:mm:ss'
                                }
                            },
                            title: {
                                display: true,
                                text: 'Timestamp'
                            }
                        },
                        y: {
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Voltage (mV)'
                            }
                        },
                        y1: {
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Current (mA)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        },
                        y2: {
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Charge (mAh)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        }
                    },
                    plugins: {
                        tooltip: {
                            mode: 'nearest',
                            intersect: false,
                            callbacks: {
                                label: function (ctx) {
                                    let label = ctx.dataset.label || '';
                                    if (label) label += ': ';
                                    label += ctx.parsed.y;
                                    if (ctx.dataset.label === 'Battery Voltage (mV)') {
                                        label += ' mV';
                                    } else if (ctx.dataset.label === 'Current (mA)') {
                                        label += ' mA';
                                    } else if (ctx.dataset.label === 'Charge (mAh)') {
                                        label += ' mAh';
                                    }
                                    return label;
                                }
                            }
                        },
                        title: {
                            text: title,
                            display: true,
                            color: '#eeee',
                            font: {
                                size: 14,
                            }
                        },
                        zoom: {
                            zoom: {
                                wheel: { enabled: true },
                                pinch: { enabled: true },
                                mode: 'x',
                            },
                            pan: {
                                enabled: true,
                                mode: 'x',
                            },
                            limits: {
                                x: { min: 'original', max: 'original' },
                                y: { min: 'original', max: 'original' }
                            }
                        }
                    }
                }
            });

        } catch (err) {
            console.error('Error rendering chart:', err);
        }
    });

    Chart.register(ChartZoom);
}

// ---- Error Flash Handling ----
function initErrorHandler() {
    // The error flash container
    const errorFlash = document.querySelector('.err-flash');

    if (errorFlash) {
        // Add an event listener to trigger every time after content was loaded
        // into this container.
        errorFlash.addEventListener('htmx:afterSwap', function (evt) {
            // Show the error container by adding the "visible" class and
            // clearing any previous slide-out state
            errorFlash.classList.add('visible');
            errorFlash.classList.remove('slide-out');

            // Clear any existing timer
            if (errorFlash._fadeoutTimer) {
                clearTimeout(errorFlash._fadeoutTimer);
            }

            // Start new timer to trigger the slide-out animation
            errorFlash._fadeoutTimer = setTimeout(() => {
                errorFlash.classList.add('slide-out');
                errorFlash._fadeoutTimer = null;
            }, 5000);
        });

        // Manual dismiss (click to dismiss the error)
        errorFlash.addEventListener('click', function () {
             // Stop the timer if the user clicks and it still exists
            if (errorFlash._fadeoutTimer) {
                clearTimeout(errorFlash._fadeoutTimer);
                errorFlash._fadeoutTimer = null;
            }
            // Trigger the slide-out animation
            errorFlash.classList.add('slide-out');
        });

        // Listen for the completion of the slide-out animation
        errorFlash.addEventListener('animationend', function () {
            if (errorFlash.classList.contains('slide-out')) {
                // The slide-out animation has finished. Reset the state
                errorFlash.classList.remove('visible');
                errorFlash.classList.remove('slide-out');
            }
        });

    }
}

// ---- Initialize everything ----
function init() {
    initChartHandler();
    initErrorHandler();
}

document.addEventListener('DOMContentLoaded', init);
