// homepage.js scripts the pages homepage.html and search/Featured.html
// Both pages rely on ./assets/Homepage.json

import {configureLinks} from './frame.js';

const DEBUG = false;

let gHomepageDatabase = null; // The global database, loaded from assets/HomepageDatabase.json

let todaysExcerpt = 0; // the featured excerpt currently displayed on the homepage
let currentExcerpt = 0; // The featured excerpt currently displayed on search/Featured.html

function initializeTodaysExcerpt() {
    // Calculate which featured excerpt to display based on today's date

    todaysExcerpt = 0;
    currentExcerpt = todaysExcerpt;
}

function displayFeaturedExcerpt() {
    // Display the html code for current featured excerpt

    let excerptCount = gHomepageDatabase.excerpts.length;
    let excerptToDisplay = ((currentExcerpt % excerptCount) + excerptCount) % excerptCount

    let displayArea = document.getElementById("random-excerpt");
    displayArea.innerHTML = gHomepageDatabase.excerpts[excerptToDisplay].html;
    configureLinks(displayArea,"indexes/homepage.html");

    let titleArea = document.getElementById("page-title");
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

function displayNextFeaturedExcerpt(increment) {
    // display the next or previous (increment = -1) random excerpt
    currentExcerpt += increment;

    displayFeaturedExcerpt();
}

export async function loadHomepage() {
    // Called when pages are loaded. Load gHomepageDatabase and wire the needed elements

    if (!gHomepageDatabase) {
        await fetch('./assets/HomepageDatabase.json')
        .then((response) => response.json())
        .then((json) => {
            gHomepageDatabase = json; 
            debugLog("Loaded homepage database.");
        });
        initializeTodaysExcerpt()
    }

    // This code runs only for search/Featured.html
    let prevButton = document.getElementById("random-prev");
    let nextButton = document.getElementById("random-next");
    if (prevButton || nextButton) {
        prevButton.onclick = () => { displayNextFeaturedExcerpt(-1); };
        nextButton.onclick = () => { displayNextFeaturedExcerpt(1); };
        displayNextFeaturedExcerpt(0);
    }

    // This code runs only for homepage.html
    let displayArea = document.getElementById("todays-excerpt");
    displayArea.innerHTML = gHomepageDatabase.excerpts[todaysExcerpt].shortHtml;
}
