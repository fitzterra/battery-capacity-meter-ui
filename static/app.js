
/**
 * Application JS
 **/

let currentChart = null; // Track the current chart instance

document.addEventListener('DOMContentLoaded', function () {
    document.body.addEventListener('htmx:afterOnLoad', function (evt) {
        const plotter = document.querySelector('.plotter');
        const canvas = plotter.querySelector('.battery-plot');

        try {
            // Read the raw JSON string that was swapped into the <canvas>
            const json = canvas.textContent.trim();

            // Parse it
            const data = JSON.parse(json);

            // Make up a title from the cyucle and cycle number
            const title = `${data.cycle} cycle ${data.cycle_num}`

            // Clear the canvas content
            canvas.innerHTML = '';

            if (!data.success) {
                canvas.insertAdjacentHTML('afterend', `<p>Error: ${data.msg}</p>`);
                return;
            }

            // Convert timestamps and values into chart format
            const voltageData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.bat_v
            }));

            // Convert timestamps and values into chart format
            const capacityData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.mah
            }));

            const currentData = data.plot_data.map(entry => ({
                x: parseInt(entry.timestamp),
                y: entry.current 
            }));
            
            const ctx = canvas.getContext('2d');

            // Destroy the previous chart if it exists
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
                            yAxisID: 'y1',
                            borderColor: 'rgb(255, 206, 86)', // yellow-ish
                            tension: 0.2,
                            pointRadius: 0
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
                                wheel: {
                                    enabled: true,
                                },
                                pinch: {
                                    enabled: true
                                },
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
});
