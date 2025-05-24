/**
 * Simple pico.css based confirmation dialog for use with HTMX.
 *
 * This package replaces the ugly browser default confirmation dialog used for
 * the hx-confirm attribute, with a nicer Pico.css dialog.
 *
 * To use it do the following:
 *
 * 1. Install as a script in the main document head section:
 * 
 *    <script src='static/js/htmx-pico-confirm.js><script>
 *
 *    This will wait for the DOM to be ready, and then ass the dialogHTML as
 *    the Pico dialog to the top of the DOM, add an event listener for
 *    htmx:confirm events. This event listener is called on all htmx events,
 *    but on targets where the hx-confirm attribute is defined on will activate
 *    the dialog.
 *
 * 2. To use the dialog, use the hx-confirm attribute. Here is an example:
 *
 *        <button
 *          class="outline contrast"
 *          data-confirm-title="Confirm Events Deletion"
 *          hx-confirm="Once deleted, these events can not be recovered again.
 *                      <br>Are you sure you want to continue?"
 *          hx-get="del_events"
 *          hx-target="closest div"
 *          hx-swap="innerHTML"
 *        >Delete all these events</button>
 *
 *    The following attributes on the button or element using hx-confirm can be
 *    used to dynamically change dialog contents:
 *
 *    * hx-confirm : This is the message to display in the dialog. Defaults to "Are you sure?"
 *    * data-confirm-title: The dialog title. Defaults to "Please Confirm"
 *    * data-confirm-ok: The text for the OK button. Defaults to "OK"
 *    * data-confirm-cancel: The text for the Cancel button. Defaults to "Cancel"
 *    * data-confirm-icon: An optional icon to show above the message. Defaults to ""
 *
 *    The contents for all but the two buttons can be HTML content. The button
 *    content is added as plain text.
 **/

(function () {
    // 1. Create dialog HTML
    const dialogHTML = `
        <dialog id="custom-confirm-dialog">
            <article>
                <header>
                    <strong id="custom-confirm-title">Please Confirm</strong>
                </header>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span id="custom-confirm-icon" style="font-size: 1.5rem;"></span>
                    <p id="custom-confirm-message">Are you sure?</p>
                </div>
                <footer>
                    <div class="grid">
                        <button id="custom-confirm-cancel" class="secondary">Cancel</button>
                        <button id="custom-confirm-ok">OK</button>
                    </div>
                </footer>
            </article>
        </dialog>`;

    // Setup function called when the DOM is ready
    function initConfirmDialog() {

        // Add the dialogHTML as in a div at the top of the DOM
        const container = document.createElement("div");
        container.innerHTML = dialogHTML.trim();
        document.body.appendChild(container.firstChild);

        // Quick access to all the replaceable content items in the dialog
        const dialog = document.getElementById("custom-confirm-dialog");
        const okButton = document.getElementById("custom-confirm-ok");
        const cancelButton = document.getElementById("custom-confirm-cancel");
        const title = document.getElementById("custom-confirm-title");
        const message = document.getElementById("custom-confirm-message");
        const icon = document.getElementById("custom-confirm-icon");

        // Hook into HTMX confirm event
        document.body.addEventListener("htmx:confirm", function (evt) {
            // Only trigger for elements with the hx-confirm attribute
            // See: https://htmx.org/events/#htmx:confirm
            if (!evt.target.hasAttribute('hx-confirm')) return;

            // Prevent the default confirm dialog from showing
            evt.preventDefault();

            // Read attributes from the target element
            const el = evt.target;
            const confirmMessage = el.getAttribute("hx-confirm") || "Are you sure?";
            const confirmTitle = el.getAttribute("data-confirm-title") || "Please Confirm";
            const confirmOK = el.getAttribute("data-confirm-ok") || "OK";
            const confirmCancel = el.getAttribute("data-confirm-cancel") || "Cancel";
            const confirmIcon = el.getAttribute("data-confirm-icon") || "";

            // Set dialog content
            title.innerHTML = confirmTitle;
            message.innerHTML = confirmMessage;
            okButton.textContent = confirmOK;
            cancelButton.textContent = confirmCancel;
            icon.innerHTML = confirmIcon;

            // Show the dialog and focus the OK button
            dialog.showModal();
            setTimeout(() => okButton.focus(), 0);

            // Cleanup function to call after a button has been pressed
            function cleanup() {
                okButton.onclick = null;
                cancelButton.onclick = null;
            }

            // Click event for the OK button.
            // See https://htmx.org/events/#htmx:confirm for how to continue
            // the confirmation request when OK is clicked.
            okButton.onclick = () => {
                dialog.close();
                cleanup();
                evt.detail.issueRequest(true);  // Proceed with HTMX request
            };

            // On calcel we simply close the dialog and clean up.
            cancelButton.onclick = () => {
                dialog.close();
                cleanup();
            };
        });
    }

    // Wait for DOM if necessary and then set things up.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initConfirmDialog);
    } else {
        initConfirmDialog();
    }
})();
