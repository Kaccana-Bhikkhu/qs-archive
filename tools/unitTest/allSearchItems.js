import {ExcerptSearcher} from '../../pages/js/search.js';

let gDatabase = null;
let gSearcher = null;

function showStatus(text) {
    let statusFrame = document.getElementById('status');

    statusFrame.innerHTML = text;
}

function showResults(text) {
    let resultsFrame = document.getElementById('results');

    resultsFrame.innerHTML = text;
}

async function loadDatabase() {
    // Called when a search page is loaded. Load the database, configure the search button,
    // fill the search bar with the URL query string and run a search.

    if (!gDatabase) {
        await fetch('../../pages/assets/SearchDatabase.json')
        .then((response) => response.json())
        .then((json) => {
            gDatabase = json;
            showStatus(`Loaded search database. Keys: ${Object.keys(gDatabase)}`);
            gSearcher = new ExcerptSearcher();
            gSearcher.loadItemsFomDatabase(gDatabase);
        });
    }
}

function showSearchItems() {
    let itemCount = 100;
    let htmlBits = [`First ${itemCount} items:`];
    for (let item of gSearcher.items.slice(0,itemCount)) {
        htmlBits.push(item.html);
        htmlBits.push("<hr>");
        htmlBits.push(item.blobs.map(String).join("<hr>"));
        htmlBits.push("<hr>");
        for (let b in item.sortBlob) {
            htmlBits.push(`${b} (${item.sortBlob[b].count}): ${item.sortBlob[b].blob}`);
        }
        htmlBits.push("<hr>");
    }
    showResults(htmlBits.join(""));
}

let startButton = document.getElementById("start-button");
startButton.onclick = () => { 
    loadDatabase().then(() => {
        showSearchItems();
    }) 
}
startButton.click()