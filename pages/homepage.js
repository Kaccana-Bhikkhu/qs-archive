import {configureLinks} from './frame.js';

const DEBUG = false;

let gDatabase = null; // The global database, loaded from assets/Homepage.json

let currentExcerpt = 0; // The excerpt currently displayed

function displayExcerpt() {
    // Display the html code for current excerpt

    let excerptCount = gDatabase.excerpts.length;
    let excerptToDisplay = ((currentExcerpt % excerptCount) + excerptCount) % excerptCount

    let displayArea = document.getElementById("random-excerpt");
    displayArea.innerHTML = gDatabase.excerpts[excerptToDisplay].html;
    configureLinks(displayArea,"indexes/homepage.html");

    let titleArea = document.getElementById("date-title");
    let title = "Today's featured excerpt:"
    if (currentExcerpt > 0)
        title = `Random excerpt (${currentExcerpt}):`;
    else if (currentExcerpt < 0) {
        let pastDate = new Date();
        pastDate.setDate(pastDate.getDate() + currentExcerpt);
        title = `Excerpt featured on ${pastDate.toDateString()}:`;
    }

    titleArea.innerHTML = title;
}

export async function loadHomepage() {
    // Called when the search page is loaded. Load the random excerpt database
    // and configure the forward and back buttons

    let prevButton = document.getElementById("random-prev");
    if (!prevButton)
        return; // Exit if the previous excerpt button isn't found.
    let nextButton = document.getElementById("random-next");

    prevButton.onclick = () => { displayNextExcerpt(-1); };
    nextButton.onclick = () => { displayNextExcerpt(1); };

    if (!gDatabase) {
        await fetch('./assets/Homepage.json')
        .then((response) => response.json())
        .then((json) => {
            gDatabase = json; 
            debugLog("Loaded random excerpt database.");
        });
    }
    displayNextExcerpt(0);
}

function displayNextExcerpt(increment) {
    // display the next or previous (increment = -1) random excerpt
    currentExcerpt += increment;

    displayExcerpt(currentExcerpt);
}