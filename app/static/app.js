/**
 * Application JS
 **/
let currentChart = null; // Track the current chart instance


/**
 * Shows the spinner overlay normally shown for HTMX calls to the backend.
 *
 * For the HTMX flow, the overlay still allows full interaction with the page
 * behind it.
 *
 * When calling this function show it, we disable any interaction with the page
 * in the background.
 *
 * Close it again via the hideSpinner() function.
 ***/
function showSpinner() {
    // Get the spinner overlay element
    const spinner = document.querySelector('.loading-overlay');

    // Normal view has it displayed full screen, but the opacity set to 0, so
    // we set the opacity to 1.
    spinner.style.opacity = '1';
    // The reason the overlay is displayed full screen, but still allows
    // interaction with the background page is because pointerevents are set to
    // 'none' which ignores these and passes it through to the background page.
    // We change it to 'auto' here to intercept the events on the overlay.
    spinner.style.pointerEvents = 'auto';  // enable interaction block
    // Do not allow the page in the background to scroll.
    document.body.style.overflow = 'hidden';  // disable scrolling
}

/**
 * Closes the spinner overlay opened by showSpinner().
 *
 * We also reset the functionality so that HTMX usage will again allow
 * interaction with the page in the background. See showSpinner().
 **/
function hideSpinner() {
    const spinner = document.querySelector('.loading-overlay');
    spinner.style.opacity = '0';
    spinner.style.pointerEvents = 'none';  // reset interaction
    document.body.style.overflow = '';      // re-enable scrolling
}

/**
 * Clears and hides the canvas element passed in.
 *
 * Args:
 *  canvas: A <canvas> element to clear and hide.
 **/
function clearCanvas(canvas) {
    canvas.hidden = true;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

/**
 * Delay function in async flows.
 *
 * Call as:
 *
 *  await sleep(1000);
 *
 **/
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Webcam handler.
 *
 * Allows you to start and stop the webcam.
 *
 * If the user has not already allowed webcam access, the browser will ask the
 * user to give give this permission first.
 *
 * Args:
 *  video: A <video> element to use for displaying the webcam video steam.
 *
 * Returns:
 *  An object with two methods:
 *      start(): This is an async method to start the webcam.
 *               Call with `res = await cam.start()`
 *               It return true if the cam was started, false otherwise and an
 *               alert will be shown with the reason for failure.
 *      stop(): Stops the webcam stream.
 *              Call with `cam.stop()`
 **/
function webCam(video) {
    // Will be used for the media stream from the camera
    let stream = null;

    // Starts the webcam and streams the video to the video element.
    async function start() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = stream;
            await video.play();
            return true;
        } catch (err) {
            console.error('Webcam error:', err);
            alert(`Unable to access webcam. Error: ${err}`);
        }
        // Error opening webcam
        return false;
    }

    // Stops the webcam stream and reset the video element steam attribute to
    // null.
    function stop() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
            video.srcObject = null;
        }
    }

    // Return an object with start and stop methods.
    return {start, stop}
}

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
    const modal = document.querySelector('dialog.bat-img');
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

    // Set up a webcam instance for streaming to the video element
    const cam = webCam(video);

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

    async function openModal() {
        // Show the spinner overlay while we open the cam
        showSpinner();
        let res = await cam.start();
        hideSpinner();

        // Camera opened OK?
        if (! res) {
            await closeModal();
            return;
        }

        modal.showModal();
        setState('capture');
    }

    async function closeModal() {
        modal.close();
        cam.stop();
        clearCanvas(canvas);
        if (cropper) cancelCropping();
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
        cam.stop();
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
                await closeModal();
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
        const errBox = document.querySelector('dialog.bat-img .error-msg');

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

// ---- Battery Label Scanning Handling ----
function initBatLabelScan() {
    // Find the modal, video and canvas elements
    const modal = document.querySelector('dialog.scan-label');
    const video = modal.querySelector('video');
    const canvas = modal.querySelector('canvas');
    const seeing = modal.querySelector('p.seeing span');
    // This is the number of digits we expect in the label.
    const labelDigits = 10;
    // The OCR can be quite noisy, so we look for a string that is exactly 10
    // digits, anchored at the start or end of the OCRd text, or preceded or
    // followed by any non digit characters line non-printable characters, etc.
    // This does not handle labels with spaces or text in them like is possible
    // with the lable generator on the Battery Controller, but those are mainly
    // used for testing.
    // If we will allow labels with non digits later, this regex needs to be
    // updated.
    const labelPattern = new RegExp(`(?:^|\\D)(\\d{${labelDigits}})(?:\\D|$)`);

    // Set up a webcam instance for streaming to the video element
    const cam = webCam(video);

    // This will be the tessarect worker we set up in startScan
    let ocr_worker = null;

    // Will be used for the media stream from the camera
    let stream = null;

    // Will be set to the matched label if any matches are made
    let label = null;

    async function openModal() {
        // Make sure to reset the match label
        label = null;
        let err = null;

        // Open the webcam while showing a spinner
        showSpinner();
        const res = await cam.start();

        // If the webcam was opened successfully, we can continue
        if (res === true) {
            // Creating the tessarect worker takes some time, but we keep
            // showing the spinner until we have this set up and no errors.
            try {
                ocr_worker = await Tesseract.createWorker('eng');
                await ocr_worker.setParameters(
                    {
                        tessedit_char_whitelist: '0123456789'
                    }
                );
            } catch(err) {
                alert(`Error setting up the OCR worker:: ${err}`);
            }

            hideSpinner();

            if (! err) {
                // Now we're good to go
                modal.showModal();
                await scanLoop();
            }
        }

        // Close the modal and clean up
        await closeModal();
    }

    async function closeModal() {
        cam.stop();
        modal.close();
        // Terminate the OCR worker if we have one running
        if (ocr_worker !== null) {
            await ocr_worker.terminate();
            ocr_worker = null;
        }
        clearCanvas(canvas);

        // Did we get a label?
        if (label !== null) {
            console.log("will search for label: ", label);
            // Start a search using the label.
            window.location.href = `/bat/?search=${label}`;
        }
    }

    async function scanLoop() {
        // Get the canvas context and set the canvas to the video size.
        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        // The OCR test we get back
        let text = '';

        while (true) {
            // Draw an image from the video stream onto the canvas.
            context.drawImage(video, 0, 0);

            // Do OCR
            try {
                // Destructuring without const or let requires parentheses - stupid JS :-(
                // This sets text to anything that was recognized.
                ({ data: { text } } = await ocr_worker.recognize(canvas));
            } catch(err) {
                console.log("Error doing recognitions: ", err);
                await sleep(200);
                continue;
            }

            // Show the text we are currently seeing as visual feedback,
            // replacing any non printable characters with a symbol
            seeing.textContent = text.replace(/[^\x20-\x7E]/g, '⎋');

            // Check if we matched a label
            const match = text.match(labelPattern);

            if (match) {
                console.log("Matched ID:", match[1]);
                // We matched the label pattern. Set label to the match and
                // exit
                label = match[1];
                break;
            }
            // Sleep for a bit
            await sleep(50);
        }
    }

    // Export the openModal and closeModal functions to be used outside.
    window.scanLabel = openModal;
    window.closeScanLabel = closeModal;
}

// ---- Initialize everything ----
function init() {
    initChartHandler();
    initErrorHandler();
    initBatImgCapModal();
    initBatLabelScan();
}

document.addEventListener('DOMContentLoaded', init);
