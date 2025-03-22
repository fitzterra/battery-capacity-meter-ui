/**
 * Main SPA code
 **/

const history = [];
/**
 * This object contains information about all endpoints that return tabular
 * data and should be auto placed in a table.
 *
 * Theses endpoints are expected to return a JSON string defining a list of
 * table rows.
 * The first row should be a list of table headers as strings.
 * The remaining rows are lists of the cell values for that row.
 *
 * Each attribute in the tabular_endpoints object is one such endpoint and
 * defines all the information such as endpoint path/URL, 
 **/
const tabular_endpoints = {
    battery_ids: {
        // This has to be an arrow function that accepts an item id and returns
        // the endpoint path including the ID. For `battery_ids` there is no
        // id, so we just return the endpoint path as is.
        endpoint: (id) => "/api/battery_ids",
        caption: (id) => "Available Battery IDs",
        spinner_text: "Loading battery IDs...",
        // The whole row is clickable
        click_cells: (row) => [],
        row_callback: (row) => renderAPITable('soc_events', row[0]),
    },
    soc_events: {
        // This has to be an arrow function that accepts an item id and returns
        // the endpoint path including the ID. For `battery_ids` there is no
        // id, so we just return the endpoint path as is.
        endpoint: (id) => `/api/soc_events/${id}`,
        caption: (id) => `SoC events for Battery ID: ${id}`,
        spinner_text: "Loading soc events...",
        // The row is only clickable if there is a UID in column 4
        // click_cells: (row) => !row[3] ? false : [],
        click_cells: (row) => {
            // Cant do anything if we do not have UID
            if (!row[3]) return false;

            // We can click on the UID
            const cells = [3];
            // Is this also dis/charge event?
            if (row[4] === 'Charging' || row[4] === 'Discharging') cells.push(4);

            return cells;
        },
        // UID for measures is in 4th column
        row_callback: (clicked) => {
            if (clicked[0] === 3) {
                renderAPITable('soc_measures', clicked[1]);
            } else {
                alert("Not so fast, buddy, still working on a graph....");
            }
        },
    },
    soc_measures: {
        // This has to be an arrow function that accepts an item id and returns
        // the endpoint path including the ID. For `battery_ids` there is no
        // id, so we just return the endpoint path as is.
        endpoint: (id) => `/api/soc_measures/${id}`,
        caption: (id) => `SoC measures for SoC UID: ${id}`,
        spinner_text: "Loading soc measures...",
    }
}

/**
 * Makes an HTTP GET request to the endpoint path supplied.
 *
 * The endpoint is expected to return a JSON object which will be parsed
 * into a object.
 *
 * Any errors will be logged to the console and an Alert will shown with the
 * error.
 *
 * Args:
 *  endpoint: The API endpoint path as a string
 * 
 * Returns:
 *  The API response as an object.
 *
 **/
async function httpGET(endpoint) {
    try {
        // Default method is GET
        const response = await fetch(endpoint);

        if (!response.ok) {
            throw new Error(`HTTP is not OK: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        const msg = `Error calling ${endpoint} endpoint : ${error}`;
        console.error(msg);
        alert(msg);
    }
}


/**
 * Adds a loader spinner to the .main-content element after clearing out the
 * old content.
 * Call this before making API calls.
 *
 * Args:
 *  text: An optional string to display with the loading spinner.
 **/
function showTableAPISpinner(text = "") {
    // Find the target element and clear it.
    const target = document.querySelector(".main-content");
    target.innerHTML = "";

    // Create a div to show the loading spinner
    const div = document.createElement("div");

    // Set the spinner by setting the aria-busy attribute. Pico.css will render the spinner.
    div.setAttribute('aria-busy', 'true');

    // Add the spinner class
    div.classList.add('spinner');

    // Add the text to display if available.
    if (text) {
        div.textContent = text;
    }

    // Append the spinner div to the target element
    target.appendChild(div);
}

async function renderAPITable(name, item_id="") {

    // First we get the API config
    const api_conf = tabular_endpoints[name]

    // Show the spinner
    showTableAPISpinner(api_conf.spinner_text);

    // Call the endpoint and get the data
    const data = await httpGET(api_conf.endpoint(item_id));

    // Get the target element into which we will render the table data, and
    // clear it our
    const target = document.querySelector(".main-content");
    target.innerHTML = "";

    // Create the table element and set a dataset-name to the current name
    const table = document.createElement("table");
    table.dataset.name = name

    const caption = document.createElement("caption");
    caption.textContent = api_conf.caption(item_id);
    table.appendChild(caption);

    // Create the thead and first tr elements
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    
    // Split the headers row from the data, and add the th elements for each
    // header column
    const headers = data.shift();
    headers.forEach(header => {
        const th = document.createElement("th");
        th.textContent = header;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Now the table body
    const tbody = document.createElement("tbody");

    // Used to figule which cells to make clickable
    let click_cells;

    // Add a tr for each data row
    data.forEach(row => {
        // If the API config has a click_cells property, we expect it to be a
        // function that returns a list of cells indexes for the row that are
        // clickable, and empty array if the whole row is clickable, or false
        // if not clickable.
        click_cells = api_conf.click_cells ? api_conf.click_cells(row) : false;

        const tr = document.createElement("tr");
        // Add the cells for each data column
        row.forEach((cell, index) => {
            const td = document.createElement("td");
            td.textContent = cell;
            tr.appendChild(td);
            // Is this cell a link target?
            if (click_cells !== false && click_cells.indexOf(index) !== -1) {
                td.classList.add('clickable');
                td.addEventListener("click", () => {
                    history.push([name, item_id]);
                    api_conf.row_callback([index, cell]);
                });
            }
        });
        // Only make the row clickable if click_cells is the empty list
        if (click_cells !== false && click_cells.length === 0) {
            tr.addEventListener("click", () => {
                history.push([name, item_id]);
                api_conf.row_callback(row)
            });
            tr.classList.add('clickable');
        }
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    target.appendChild(table);

    // The back button
    if (history.length) {
        const last = history[history.length - 1];

        const button = document.createElement("button");
        button.textContent = "Back";
        button.addEventListener("click", () => {
            // We are using this history element, so remove it from the list
            history.pop();
            renderAPITable(last[0], last[1])
        });
        table.after(button);
    }
}

/**
 * The main application entry point.
 **/
async function main() {
    // We start by rendering the available batteries
    await renderAPITable('battery_ids');
}


/**
 * We start the main application as soon as the dom is loaded.
 **/
document.addEventListener("DOMContentLoaded", async () => {
    await main();
});

