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
            // If the json data is the empty string, this is not a plot update,
            // but the first time loading the view and canvas. In this casewe
            // can just return
            if (json === "") return;

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

// ---- Battery Image Capture Handling ----
function initBatImgCapModal() {

    const modal = document.querySelector('.bat-img-modal');
    const video = modal.querySelector('.cam-stream');
    const canvas = modal.querySelector('.cam-canvas');
    const takeBtn = modal.querySelector('.btn-capture');
    const cropBtn = modal.querySelector('.btn-crop');
    const saveBtn = modal.querySelector('.btn-save');
    const rotLeftBtn = modal.querySelector('.btn-rotate.left');
    const rotRightBtn = modal.querySelector('.btn-rotate.right');
    const applyBtn = modal.querySelector('.btn-apply');
    const backBtn = modal.querySelector('.btn-back');
    const cancelBtns = modal.querySelectorAll('[data-cancel]');
    // We expect the max image upload size to be set on the div.video-wrapper
    // element as `data-max-size="nnnn"`
    const maxSize = parseInt(document.querySelector('.video-wrapper').dataset.maxSize, 10);

    // A list of all buttons that we control via the setState function
    const buttons = [takeBtn, cropBtn, applyBtn, rotLeftBtn, rotRightBtn, backBtn, saveBtn];
    // An array to define which button should be shown for each possible state
    const button_states = {
        'capture': [takeBtn],
        'save': [cropBtn, saveBtn],
        'cropping': [rotLeftBtn, rotRightBtn, applyBtn, backBtn],
    }

    // Will be used for the media stream from the camera
    let stream = null;
    // Used for the Cropper instance created in startCropping
    let cropper = null;
    // This will be image we create from the camera stream on which cropping
    // will be done. Created in startCropping, cleanup up in applyCrop and
    // cancelCropping
    let croppingImage = null;
    // The current state we're in.
    let state = null;

    function openModal() {
        modal.showModal();
        startWebcam();
        setState('capture');
    }

    function closeModal() {
        modal.close();
        stopWebcam();
        clearCanvas();
        if (cropper) cancelCropping();
    }

    function startWebcam() {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(mediaStream => {
                stream = mediaStream;
                video.srcObject = stream;
                video.play();
            })
            .catch(err => {
                console.error('Webcam error:', err);
                alert('Unable to access webcam');
                closeModal();
            });
    }

    function stopWebcam() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
            video.srcObject = null;
        }
    }

    function clearCanvas() {
        canvas.hidden = true;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        video.hidden = false;
    }

    /**
     * Captures a single frame from the video feed and puts it onto the canvas
     * after resizing the canvas to the image size.
     *
     * Also changes state to allow saving or cropping the image.
     ***/
    function captureFrame() {
        // Get the current videa feed width and height
        const width = video.videoWidth;
        const height = video.videoHeight;

        // Set the tp the video feed size
        canvas.width = width;
        canvas.height = height;

        // Copy the current frame from the vide feed into the canvas
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, width, height);

        // Hide the video feed and show the canvas
        video.hidden = true;
        canvas.hidden = false;
        
        // Stop the webcam and change to the save image state which will allow
        // detouring to cropping.
        stopWebcam();
        setState('save');
    }

    /**
     * Starts a cropping operation on the saved image on the canvas.
     *
     * A new image is created from the canvas, a cropper is started and the
     * crop state is entered.
     **/
    function startCropping() {
        // Create a new temp image in croppingImage from the current canvas so
        // that we can start a cropper on this image.
        // WE add the croppingImage to the same parent as the canvas, but then
        // hide the canvas.
        const dataURL = canvas.toDataURL('image/png');
        croppingImage = document.createElement('img');
        croppingImage.classList.add('cropping-image');
        croppingImage.src = dataURL;
        canvas.parentNode.appendChild(croppingImage);
        canvas.hidden = true;

        // Start the cropper instance on croppingImage
        cropper = new Cropper(croppingImage, {
            viewMode: 1, // Cropbox restricted to crop canvas size
            dragMode: 'move', // Also allow background image to be dragged
        });

        // Change the state
        setState('cropping');
    }

    function rotate(evt) {
        // Rotation is -1 deg for left rotate button, 1 deg for right rotate
        // button.
        const rot_angle = evt.currentTarget.classList.contains('left') ? -1 : 1;
        cropper.rotate(rot_angle);
    }

    /**
     * Applies the cropping selection by copying that area to the canvas and
     * then destroying the cropper and temp croppingImage.
     *
     * Changes state back to the save state.
     **/
    function applyCrop() {
        // Copy the cropper canvas to our main canvas after setting the correct
        // size.
        const croppedCanvas = cropper.getCroppedCanvas();
        canvas.width = croppedCanvas.width;
        canvas.height = croppedCanvas.height;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(croppedCanvas, 0, 0);

        // Clean up.
        cropper.destroy();
        cropper = null;
        croppingImage.remove();
        croppingImage = null;
        canvas.hidden = false;

        // Make the cropped image fit the container so we see the full cropped
        // part and not a zoomed in view meant to fill the container.
        document.querySelector(".video-wrapper canvas.cam-canvas")
            .style.objectFit = "contain";

        setState('save');
    }

    function cancelCropping() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        if (croppingImage) {
            croppingImage.remove();
            croppingImage = null;
        }
        canvas.hidden = false;
        setState('save');
    }

    /**
     * Saves the image by pulling it from the canvas, scaling it down if needed
     * (based on the maxSize constant defined above) and then POSTS it to the
     * backend as a JPEG image
     **/
    async function saveImage() {

        // Get initial image data as a JPEG at 0.9 quality value
        let rawImg = await new Promise(resolve =>
            canvas.toBlob(b => resolve(b), 'image/jpeg', 0.9)
        );

        console.log(`Image size is ${rawImg.size}b and max size allowed is ${maxSize}b.`);
        // Check size and scale if needed.
        if (rawImg.size > maxSize) {
            console.log(`Image width is ${canvas.width}px, height is ${canvas.height}px.`);
            // We need to scale the image, but we can not simply scale it
            // linearly based on the ratio it is larger than the original.
            // For this reason we use an exponential function to scale so that
            // we have a smaller scale factor the closer the image is to the
            // max size, with the scale factor rising exponentially the larger
            // the source image is.
            // The `beta` value here determines how aggressive the scaling is.
            // For the two webcams I tested, this seems to a good ratio. It
            // seems for high definition webcams, the scaling needs to be a bit
            // more aggressive than for lower def ones, so for my HD webcam
            // this beta still overshoots the final size by about 1% for full
            // size images. This is OK since we will allow a 5% or so tolerance
            // on the backend.
            const beta = 0.6;
            // This is the ratio between the max and current size. The smaller
            // the ration, the larger the source image
            const ratio = maxSize / rawImg.size;
            // Calculate the scaling factor exponentially using the beta value,
                // peaking to a scale of 1 if need be. The smaller the ratio
            // is, the smaller we will scale. As the ration gets closer to 1,
            // we taper off the scaling exponentially.
            const scale = Math.min(1, ratio ** beta);

            // Create a new canvas to host the scaled image
            const scaledCanvas = document.createElement('canvas');
            const ctx = scaledCanvas.getContext('2d');

            // Scale the new canvas and copy from the main canvas to this new
            // canvas.
            scaledCanvas.width = Math.floor(canvas.width * scale);
            scaledCanvas.height = Math.floor(canvas.height * scale);
            ctx.drawImage(canvas, 0, 0, scaledCanvas.width, scaledCanvas.height);

            // Reassign rawImg to the scaled canvas - this is the image we will
            // POST to the backend
            rawImg = await new Promise(resolve =>
                scaledCanvas.toBlob(b => resolve(b), 'image/jpeg', 0.9)
            );
            console.log(`Scaled width is ${scaledCanvas.width}px, height is ${scaledCanvas.height}px.`);
            console.log(`Scaled size is ${rawImg.size}b`);
            console.log(`Scale factor: ${scale}`);
        }

        // Upload the final rawImg
        const formData = new FormData();
        formData.append('image', rawImg, 'upload.jpg');

        try {
            const response = await fetch('img', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                // All good, we can close the modal and refresh the page
                console.log('Upload successful');
                closeModal();
                location.reload();
            } else {
                let errorText = await response.text();
                if (errorText.length > 300) {
                    errorText = errorText.slice(0, 300) + '…'
                }
                const msg = `Upload failed (HTTP ${response.status}): ${errorText}`;
                console.error(msg);
                showErrorMessage(msg);
            }
        } catch (err) {
            showErrorMessage('Network error during upload:', err);
        }
    }


    function showErrorMessage(msg) {
        const errBox = document.querySelector('.bat-img-modal .error-msg');

        errBox.textContent = msg;
        errBox.hidden = false;

        // Force reflow so transition kicks in
        void errBox.offsetWidth;

        errBox.classList.add('show');

        setTimeout(() => {
            errBox.classList.remove('show');
            // Hide after fade out
            setTimeout(() => {
                errBox.hidden = true;
                errBox.textContent = '';
            }, 500); // match fade out time
        }, 10000); // 10 seconds
    }

    function setState(new_state) {
        if (new_state === state) return;

        // New state must be of the possible states.
        if (! Object.keys(button_states).includes(new_state)) {
            console.log("Invalid state: ", new_state);
            return;
        }

        // Set the new state
        state = new_state;

        // Hide and show buttons based on the new state
        Object.values(buttons).forEach((btn) => {
            if (button_states[state].includes(btn)) {
                btn.hidden = false;
            } else {
                btn.hidden = true;
            }
        });
    }

    takeBtn.addEventListener('click', captureFrame);
    cropBtn.addEventListener('click', startCropping);
    rotLeftBtn.addEventListener('click', rotate);
    rotRightBtn.addEventListener('click', rotate);
    applyBtn.addEventListener('click', applyCrop);
    backBtn.addEventListener('click', cancelCropping);
    saveBtn.addEventListener('click', saveImage);
    cancelBtns.forEach(btn => btn.addEventListener('click', closeModal));

    window.takeBatPic = openModal;
}

// ---- Initialize everything ----
function init() {

    initChartHandler();
    initErrorHandler();
    initBatImgCapModal();
}

document.addEventListener('DOMContentLoaded', init);
