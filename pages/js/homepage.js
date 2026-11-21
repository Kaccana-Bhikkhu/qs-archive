// homepage.js scripts the pages homepage.html and search/Featured.html
// Both pages rely on ./assets/FeaturedDatabase.json

import {configureLinks, openLocalPage, framePage, loadDatabase, frameSearch} from './frame.js';
import './autoComplete.js';
import {SearchQuery,gSearchers,loadSearchDatabase,encodeSearchQuery,addFilter,queryFromParams} from './search.js';

const DEBUG = true;
const PEEK_FUTURE = false;

let gHomepageDatabase = null; // Featured excerpt html to display on the homepage, loaded from assets/FeaturedDatabase1_.json
let gHistoryDatabase = null; // Html to display on the history page, loaded from assets/FeaturedDatabase2_.json
let gFeaturedDatabase = null; // Used to access other properties of the history database, loaded from either version of FeaturedDatabase.json
let gNavBar = null; // The main navigation bar, set after all DOM content loaded

let gTodaysExcerpt = 0; // the featured excerpt currently displayed on the homepage
let gTodaysHolidayHtml = ""; // The html text to display for today's holiday
let gSearchFeaturedOffset = 0; // The featured excerpt currently displayed on search/Featured.html
let gRandomExcerpts = []; // The random excerpts we have generated this session.

function calendarModulus(index) {
    // Return index modulo the length of the calendar

    let excerptCount = gFeaturedDatabase.calendar.length;
    return ((index % excerptCount) + excerptCount) % excerptCount;
}

function holidayHtml(date) {
    // Return the holiday html (if any) for a given Date object
    let dateStr = date.toISOString().slice(0,10);
    let holiday = gFeaturedDatabase.holiday || {}; // Prevent an exception if holiday is missing
    let message = holiday[dateStr];
    if (message)
        return `<p class = "holiday-banner">${message}</p>`;
    else
        return "";
}

let gDebugDateOffset = 0;
function initializeTodaysExcerpt(todaysDate) {
    // Calculate which featured excerpt to display based on today's date
    // todaysDate overrides today with a different date

    if (!todaysDate)
        todaysDate = new Date();
    let calendarStartDate = new Date(gFeaturedDatabase.startDate);
    let daysSinceStart = Math.floor((todaysDate - calendarStartDate) / (1000 * 3600 * 24));
    debugLog("Days since start:",todaysDate,calendarStartDate,daysSinceStart);
    gTodaysExcerpt = calendarModulus(daysSinceStart);
    gSearchFeaturedOffset = 0;

    gTodaysHolidayHtml = holidayHtml(todaysDate);
}

function displayFeaturedExcerpt() {
    // Display the html code for current featured excerpt on search/Featured.html

    let excerptToDisplay = gFeaturedDatabase.calendar[calendarModulus(gTodaysExcerpt + gSearchFeaturedOffset)];
    
    let title = "Today's featured excerpt";
    let prefix = "";
    if (gSearchFeaturedOffset > 0 && !(DEBUG && PEEK_FUTURE)) {
        let excerptCodes = Object.keys(gHistoryDatabase.excerpts);
        while (gRandomExcerpts.length < gSearchFeaturedOffset) {
            let randomIndex = Math.floor(Math.random() * excerptCodes.length);
            gRandomExcerpts.push(excerptCodes[randomIndex]);
        }
        excerptToDisplay = gRandomExcerpts[gSearchFeaturedOffset - 1];
        title = `Random featured excerpt (${gSearchFeaturedOffset})`;
    } else {
        let pastDate = new Date();
        pastDate.setDate(pastDate.getDate() + gSearchFeaturedOffset);
        prefix = holidayHtml(pastDate);
        if (gSearchFeaturedOffset != 0) {
            let options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            title = `Excerpt featured on ${pastDate.toLocaleDateString("en-us",options)}`;
        }
    }

    let displayArea = document.getElementById("random-excerpt");
    displayArea.innerHTML = prefix + gHistoryDatabase.excerpts[excerptToDisplay];
    configureLinks(displayArea,"search/homepage.html");

    let titleArea = document.getElementById("page-title");
    titleArea.innerHTML = title;
}

function displayNextFeaturedExcerpt(increment) {
    // display the next or previous (increment = -1) random excerpt
    gSearchFeaturedOffset += increment;

    displayFeaturedExcerpt();
}

// Homepage date display
function updateDate(theDate) {
    const dateElement = document.getElementById('currentDate');
    if (dateElement) {
        if (!theDate)
            theDate = new Date();
        const formattedDate = theDate.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        dateElement.textContent = formattedDate;
    }
}

// Utility Functions
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Meditation Timer
class MeditationTimer {
    constructor() {
        this.duration = 5;
        this.timeLeft = this.duration * 60;
        this.isActive = false;
        this.interval = null;
        
        this.reloadPage();
    }

    reloadPage() {
        // DOM elements must be updated each time we reload the main page
        this.timeDisplay = document.getElementById('timeDisplay');
        this.playButton = document.getElementById('timerPlayButton');
        this.resetButton = document.getElementById('resetButton');
        this.durationSlider = document.getElementById('durationSlider');
        this.durationDisplay = document.getElementById('durationDisplay');

        this.playButton.addEventListener('click', () => this.toggleTimer());
        this.resetButton.addEventListener('click', () => this.resetTimer());
        this.durationSlider.addEventListener('input', (e) => this.updateDuration(e));
        this.durationSlider.value = this.duration;
        this.durationDisplay.textContent = this.duration;

        this.updateDisplay();
    }

    toggleTimer() {
        this.isActive = !this.isActive;

        if (this.isActive) {
            this.startTimer();
        } else {
            this.pauseTimer();
        }
        this.updateDisplay();
    }

    startTimer() {
        if (!this.bell)
            this.bell = new Audio('assets/sounds/meditation-bell.mp3');
        this.interval = setInterval(() => {
            this.timeLeft--;
            this.updateDisplay();
            
            if (this.timeLeft === 0) {
                this.handleTimerComplete();
            }
        }, 1000);
    }

    pauseTimer() {
        clearInterval(this.interval);
    }

    resetTimer() {
        this.isActive = false;
        clearInterval(this.interval);
        this.timeLeft = this.duration * 60;
        
        // Update the play button icon to show play
        const playButtonIcon = this.playButton.querySelector('img');
        playButtonIcon.src = 'images/icons/play.svg';
        
        this.updateDisplay();
    }

    updateDuration(event) {
        this.duration = parseInt(event.target.value);
        this.durationDisplay.textContent = this.duration;
        if (!this.isActive) {
            this.timeLeft = this.duration * 60;
            this.updateDisplay();
        }
    }

    updateDisplay() {
        this.timeDisplay.textContent = formatTime(this.timeLeft);
        const playButtonIcon = this.playButton.querySelector('img');
        playButtonIcon.src = this.isActive ? 
            'images/icons/pause.svg' : 
            'images/icons/play.svg';
    }

    handleTimerComplete() {
        this.isActive = false;
        this.resetTimer();
        if (this.bell)
            this.bell.play().catch(error => console.log('Error playing bell:', error));
    }
}

function highlightNavMenuItem() {
    // Highlight items in the main nav menu if the appropriate page is loaded

    const pagesWithin = { // regex matches to highlight each menu item
        "Home": /^homepage/,
        "Key": /^topics|^cluster/,
        "Tags": /^tags|^drilldown|^dispatch\/Tags/,
        "Events": /^events|^dispatch\/Events/,
        "About": /^about/
    }

    let openPage = framePage();
    for (let item of gNavBar.querySelector(".main-nav").querySelectorAll("li")) {
        let firstMenuWord = item.querySelector("a").textContent.match(/[a-zA-Z]*/)[0];
        if (pagesWithin[firstMenuWord]?.test(openPage))
            item.classList.add("highlighted")
        else
            item.classList.remove("highlighted");
    }
}

function configurePopupMenus(loadedFrame) {
    // Set triggers for select.sublink-dropdown items on the page

    for (let menu of loadedFrame.querySelectorAll(".sublink-popup select")) {
        menu.addEventListener("change",function (event) {
            openLocalPage(event.target.value);
            debugLog("Selection changed to",event.target.value);
        })
    }
    for (let menu of loadedFrame.querySelectorAll(".sublink2-popup select")) {
        menu.addEventListener("change",function (event) {
            openLocalPage(event.target.value);
            debugLog("Selection changed to",event.target.value);
        })
    }
}

function loadFullDatabase(json) {
    // Fill gHomepageDatabase and gHistoryDatabase from FeaturedDatabase.json

    gFeaturedDatabase = json;
    gHomepageDatabase = {"excerpts":{}};
    gHistoryDatabase = {"excerpts":{}};
    for (let excerptCode in json.excerpts) {
        gHomepageDatabase.excerpts[excerptCode] = json.excerpts[excerptCode].shortHtml;
        gHistoryDatabase.excerpts[excerptCode] = json.excerpts[excerptCode].html;
    }
    debugLog("Loaded homepage and history databases.")
}

async function initializeHomepage() {
    // This code to configure the homepage runs only for homepage.html
    let featuredExcerptContainer = document.getElementById("todays-excerpt");
    if (!featuredExcerptContainer)
        return;
    
    if (!gHomepageDatabase) {
        await loadDatabase('FeaturedDatabase1_.json')
        .then((json) => {
            if ("made" in json) // Did we read the full database?
                loadFullDatabase(json)
            else {
                gHomepageDatabase = json;
                gFeaturedDatabase = json; 
                debugLog("Loaded homepage database.");
            }
        });
        initializeTodaysExcerpt()
    }

    gMeditationTimer.reloadPage();
    document.getElementById("details-link").addEventListener("click",function() {
        gSearchFeaturedOffset = 0; // The details link always goes to the excerpt featured on the homepage
    });
    featuredExcerptContainer.innerHTML = holidayHtml(new Date()) + gHomepageDatabase.excerpts[gFeaturedDatabase.calendar[gTodaysExcerpt]];
    configureLinks(featuredExcerptContainer,"search/homepage.html");
        // links in excerpts are relative to depth 1 pages

    updateDate();
}

async function initializeSearchFeatured() {
    // This initialization code runs only for search/Featured.html
    let prevButton = document.getElementById("random-prev");
    let nextButton = document.getElementById("random-next");
    if (prevButton || nextButton) {
        prevButton.addEventListener("click", function(event) {
            displayNextFeaturedExcerpt((event.shiftKey && DEBUG) ? -30: -1);
        });
        nextButton.addEventListener("click", function(event) {
            displayNextFeaturedExcerpt((event.shiftKey && DEBUG) ? 30: 1);
        });
        await loadDatabase('FeaturedDatabase2_.json')
        .then((json) => {
            if ("made" in json) // Did we read the full database?
                loadFullDatabase(json)
            else {
                gHistoryDatabase = json;
                gFeaturedDatabase = json; 
                debugLog("Loaded history page database.");
            }
        });
        initializeTodaysExcerpt();
        displayNextFeaturedExcerpt(0);
    }
}

export async function loadHomepage(loadedFrame) {
    // Called every time a page is loaded.
    // Load gFeaturedDatabase and wire the needed elements

    dropdownMenuClick(null); // Close all dropdown menus
    gNavBar.querySelector('.main-nav').classList.remove("active");

    highlightNavMenuItem();
    configurePopupMenus(loadedFrame);

    initializeHomepage();
    initializeSearchFeatured();
    try {
         lucide.createIcons(lucide.icons);
    } catch (err) { }

    document.querySelector("a.search-within")?.addEventListener("click",(event) => {
        event.preventDefault();
        searchWithinThisPage();
    });
}

function dropdownMenuClick(clickedItem) {
    // Toggle the menu item clicked (a div.dropdown element)
    // Close all other menus; clickedItem === null closes all menus.
    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        if (dropdownMenu === clickedItem)
            dropdownMenu.classList.toggle('menu-open');
        else
            dropdownMenu.classList.remove('menu-open');
    });

    // The same for the floating search window
    let searchWindow = document.querySelector('.floating-search');
    if (clickedItem === document.getElementById('nav-search-icon')) {
        searchWindow.classList.toggle('active');
    } else
        searchWindow.classList.remove('active');
    if (searchWindow.classList.contains('active')) {
        showFloatingSearch();
    } else {
        closeFloatingSearch();
    }
    
    // and the Abhayagiri nav menu
    if (clickedItem === document.getElementById('nav-abhayagiri-icon')) {
        document.querySelector('.abhayagiri-grid-menu').classList.toggle('active');
    } else
        document.querySelector('.abhayagiri-grid-menu').classList.remove('active');
}

function setupNavMenuTriggers() {
    // Configure javascript triggers for header elements
    gNavBar = document.getElementById('header-content');

    // Clicking on the hamburger icon toggles the main nav menu
    gNavBar.querySelector('.hamburger').addEventListener('click', function() {
        gNavBar.querySelector('.main-nav').classList.toggle('active');
        dropdownMenuClick(null); // Close all dropdown menus
    });

    // Close the dropdown menus and the main nav menu on a menu click
    gNavBar.querySelectorAll('.dropdown-content > a').forEach(function(dropdownTrigger) {
        dropdownTrigger.addEventListener('click', function() {
            this.parentElement.style.display = "none";
            gNavBar.querySelector('.main-nav').classList.remove("active");
            dropdownMenuClick(null);
        });
    });

    // Close the dropdown menus when the user clicks anywhere else
    document.addEventListener('click',function(event) {
        if (!event.target.matches('.keep-nav-menu-open, .keep-nav-menu-open *')) {
            dropdownMenuClick(null);
        }
    });

    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        dropdownMenu.querySelector(".dropdown-trigger").addEventListener('click', function() {
            dropdownMenuClick(this.parentElement);
        });
        // Re-enable hover functionality when mousing over a dropdown menu
        dropdownMenu.addEventListener('mouseenter', function() {
            this.querySelector(".dropdown-content").style.display = "";
        });
    });

    // Clicking the search button toggles the floating search bar
    document.getElementById('nav-search-icon').addEventListener('click', function() {
        dropdownMenuClick(this);
    });
    // Handle clicking the search button
    document.getElementById('floating-search-go').addEventListener('click', function(event) {
        let inputBox = document.getElementById('floating-search-input');
        inputBox.blur();
        let searchText = inputBox.value;
        inputBox.value = "";
        gQuery = "";
        debugLog('Search bar search for',searchText);
        event.preventDefault();
        runFloatingSearch(searchText)
    });

    /* Uncomment this code to begin working on #113: Grid menu matching abhayagiri.org
    // Clicking Abhayagiri icon toggles the Abhayagiri grid menu
    document.getElementById('nav-abhayagiri-icon').addEventListener('click', function() {
        dropdownMenuClick(this);
    });
    */

    // Keyboard shortcuts
    document.addEventListener("keydown", function(event) {
        // '/' key opens the search bar if it's not open already.
        // Don't open the search bar if an input box has focus.
        let header = document.querySelector('header');
        if ((["/","?"].includes(event.key)) && !header.querySelector('.floating-search.active')
                && document.activeElement.nodeName !== "INPUT") {
            event.preventDefault();
            if (event.key === "/")
                document.getElementById("nav-search-icon").click();
            else
                searchWithinThisPage();
        }
        // Esc key closes all menus if any are open
        if ((event.key === "Escape") && header.querySelector('.active')) {
            event.preventDefault();
            if (document.querySelector('.floating-search.active')) {
                // Close the search bar if it's open.
                dropdownMenuClick(document.querySelector('.floating-search'));
            } else {
                // Otherwise close everything.
                dropdownMenuClick(null);
                gNavBar.querySelector('.main-nav').classList.remove("active");
                floatMenus(gMenuFloating,false);
            }
        }
    });
}

// Global variables used by the auto complete system
let gAutoCompleteDatabase = {};     // The database loaded 
let gQuery = "";                    // The query corresponding to the text currently contained in the floating search bar
let gSearchWithinQuery = null;      // The params query we are searching within, corresponding either to the current search page query or
                                    // the query corresponding to the current excerpt page. When non-null, clicking an autocomplete item
                                    // will open the advanced search page with that item's query as an additional filter.
                                    // When null, clicking an autocomplete item jumps to the corresponding html page.
let gSearchWithinExcerpts = null;   // The excerpts found by gSearchWithinQuery (all excerpts if it's null)
let gDropDownFilters = null;        // A Map describing the filters that (might) display in the auto complete box
                                    // keys (str): the filter chip values in AutoCompleteDatabase.json
                                    // values (int): the number of excerpts in gSearchWithinExcerpts this filter matches
                                    //    null means not calculated yet
                                    // We hide filters that match no objects
                                    // null when gSearchQuery is null
let gAutoComplete = null;           // The autoComplete.js object, initialized below
const MAX_RESULTS = 15              // The maximum number of results to display

export async function showFloatingSearch(query = null,searchWithin = null,placeholder = "") {
    // Show the floating search window.
    // query: Display this as the initial query; if null, keep what the user already typed
    // searchWithin: see gSearchWithinQuery for the meaning of this parameter
    // placeholder: replaces the default prompt if provided
    // The same for the floating search window
    
    let searchWindow = document.querySelector('.floating-search');
    searchWindow.classList.add('active');
    
    let searchBar = document.getElementById('floating-search-input');
    if (query === null)
        searchBar.value = gQuery;
    else
        searchBar.value = query;
    gSearchWithinQuery = searchWithin;

    let loader = loadSearchDatabase(); // load the search database in preparation for displaying how many excerpts we've found
    if (!gAutoComplete)
        setupAutoComplete();

    searchBar.focus();
    if (searchWithin) {
        if (searchWithin.get("q").trim() || searchWithin.get("filter1"))
            searchBar.placeholder = placeholder || "Narrow this search...";
        else
            searchBar.placeholder = placeholder || "Choose a search filter...";
        let searchGroups = new SearchQuery(queryFromParams(searchWithin,false,true),searchWithin.has("strict"));

        await loader; // Make sure we have loaded the search database before proceeding.
        gSearchers["x"].search(searchGroups);
        gSearchWithinExcerpts = gSearchers["x"].foundItems;
        if (gSearchWithinExcerpts.length === gSearchers["x"].items.length)
            gSearchWithinExcerpts = null; // Special case for a search which finds all excerpts
        gDropDownFilters = new Map();

        let searchPageInput = document.querySelector("input#search-text");
        if (searchPageInput) {
            searchPageInput.value = searchWithin.get("q").trim() || "";
        }
    } else {
        searchBar.placeholder = placeholder || "Search the teachings...";
        gSearchWithinExcerpts = null;
        gDropDownFilters = null;
    }

    if (searchBar.value.trim()) // If the search bar contains text, display the auto complete menu
        setTimeout(function() {
            gAutoComplete.start();
            countFoundExcerpts();
        },200);
}

export function closeFloatingSearch() {
    // Close the floating search window.
    let searchWindow = document.querySelector('.floating-search');
    searchWindow.classList.remove('active');
    document.getElementById('floating-search-input').blur();
    displayExcerptCount(0);
}

function searchWithinThisPage() {
    // Called when the user types '?' on any page; what we do depends on which page it is.

    let page = framePage();
    
    if (page === "search/Advanced-search.html") {
        showFloatingSearch(null,frameSearch()); // Search within the current list of found excerpts
    } else if (page === "search/Text-search.html") {
        let params = frameSearch();
        let filterNumber = 1;
        while (params.has(`filter${filterNumber}`)) { // Don't apply filters hiding in the URL query when the simple search page is displayed
            params.delete(`filter${filterNumber}`);
            filterNumber += 1;
        }
        showFloatingSearch(null,params);
    } else {
        let searchWithinLink = document.querySelector("a.search-within");
        if (searchWithinLink) {
            debugLog(searchWithinLink);
            let hashRemoved = searchWithinLink.href.replace(/#[^?]*/,""); // frame.js # notation confuses the URL parser.
            let params = new URL(hashRemoved).searchParams;
            showFloatingSearch(null,params,"Search within " + searchWithinLink.innerText.trim());
        } else {
            showFloatingSearch(null,new URLSearchParams("?q=&search=all&featured&relevant"));
        }
    }

}

function runFloatingSearch (searchText) {
    // Called when the user clicks Search in the floating search bar.
    searchText = searchText.trim();
    if (gSearchWithinQuery) { // Append searchText to the existing search query
        let existingQuery = queryFromParams(gSearchWithinQuery,false,false).trim();
        existingQuery = [existingQuery,searchText].filter(s => s).join(" "); // don't add a space if one string is empty
        gSearchWithinQuery.set("q",encodeURIComponent(encodeSearchQuery(existingQuery)));
        openLocalPage("search/Advanced-search.html",String(gSearchWithinQuery));
        gSearchWithinQuery = null;
    } else { // Just open the simple search page
        let query = encodeURIComponent(encodeSearchQuery(searchText));
        openLocalPage("search/Text-search.html",`q=${query}&search=all&featured&relevant`);
    }
}

function excerptsMatchingItem(autoCompleteEntry,cacheOnly = false) {
    // Returns the number of excerpts that match this chip in the current search within environement.
    // If cacheOnly, do not run any new calculations

    if (!gSearchWithinExcerpts) // null when we are searching within all excerpts
        return autoCompleteEntry.excerptCount;
    let queryText = autoCompleteEntry.chip.split("_",4)[3]; // The last part of the chip is the query text
    if (gDropDownFilters.get(queryText) === undefined && !cacheOnly) {
        let searchQuery = new SearchQuery(queryText);
        gSearchers["x"].search(searchQuery,gSearchWithinExcerpts);
        gDropDownFilters.set(queryText,gSearchers["x"].foundItems.length); // Cache the found item count
    }
    return gDropDownFilters.get(queryText);
}

function calcExcerptsMatchingItems(entries,timeout) {
    // Call excerptsMatchingItems on all items in entries. This caches the values of that function for later use.
    // Throw a "Timeout" exception if more than timeout milliseconds pass during the exceution and we have
    // already found enough items to populate the list.
    // Return the number of entries with unique search queries.

    let start = performance.now();
    let uniqueQueries = new Set();
    for (let entry of entries) {
        if (excerptsMatchingItem(entry))
            uniqueQueries.add(entry.chip.split("_",4)[3]);
        if ((performance.now() - start) > timeout && uniqueQueries.size >= MAX_RESULTS)
            throw Error(`Timeout - ${uniqueQueries.size} found.`);
    }
    return uniqueQueries.size;
}

let gItemMatchingCallbackRef = 0; // The reference number used for this callback function
function calcMatchingItemsCallback(entries) {
    // Continue calculating matching items asynchronously using a series of callbacks until finished.

    let matchingItems;
    try {
        matchingItems = calcExcerptsMatchingItems(entries,300);
    } catch (err) {
        if (err.message.startsWith("Timeout")) { // Continue the calculation with another callback if it hasn't completed.
            gItemMatchingCallbackRef = window.setTimeout(calcMatchingItemsCallback,100,entries);
            matchingItems = err.message.match(/[0-9]+/)[0];
            document.getElementById("autocomplete-total-items").innerText = matchingItems + "+";
            return;
        } else
            throw(err);
    }
    gItemMatchingCallbackRef = 0;
    document.getElementById("autocomplete-total-items").innerText = String(matchingItems);
}

function setupAutoComplete() {
    // Code to configure floating menu autocomplete functionality
    // See https://tarekraafat.github.io/autoComplete.js/#/usage for details
    gAutoComplete = new autoComplete({
        selector: "#floating-search-input",
        //placeHolder: "Search the teachings...",
        diacritics: true, // Don't be picky about diacritics
        data: {
            src: async () => {
                try {
                    // Fetch External Data Source
                    gAutoCompleteDatabase = loadDatabase("AutoCompleteDatabase_.json")
                    return gAutoCompleteDatabase;
                } catch (error) {
                    return error;
                }
            },
            keys: ["short","long","number"],
            cache: true,
            filter: (results) => {
                // Filter entries that link to the same file
                let links = new Set();
                let filtered = results.filter((item) => {
                    return !(item.key === "number" && item.value.number !== gQuery); // Number search must match exactly
                });
                if (gSearchWithinQuery) {
                    if (gItemMatchingCallbackRef) {
                        window.clearTimeout(gItemMatchingCallbackRef);
                        gItemMatchingCallbackRef = 0;
                    }
                    filtered = filtered.filter((item) => item.value.chip); // Remove page-only items
                    let items = filtered.map((item) => item.value);
                    try { // Run a potentially long calculation to cache the matching item counts
                        calcExcerptsMatchingItems(items,300);
                    } catch (err) {
                        if (err.message.startsWith("Timeout")) {
                            gItemMatchingCallbackRef = window.setTimeout(calcMatchingItemsCallback,100,items);
                        } else
                            throw(err);
                    }
                    filtered = filtered.filter((item) => {
                        if (!excerptsMatchingItem(item.value,true))
                            return false; // Don't display filters which match no excerpts
                        let query = item.value.chip.split("_",4)[3];
                        if (links.has(query))
                            return false; // Remove items with identical queries
                        links.add(query);
                        return true;
                    });
                } else {
                    filtered = filtered.filter((item) => {
                        if (!item.value.link)
                            return false; // Remove filter-only items
                        if (links.has(item.value.link))
                            return false; // Remove items that link to identical pages
                        links.add(item.value.link);
                        return true;
                    });
                }
                debugLog(filtered.length,"items in the menu.");
                return filtered;
            },
        },
        submit: true,
        query: (input) => {
            // Don't search if the input contains blob control characters not used for other purposes
            if (/[\]\[(){}<>&^#]/.test(input)) {
                gQuery = "";
                return "";
            }

            input = input.replace(/^\s+/,""); // Strip leading whitespace
            input = input.replace(/\s+/," ") // Convert all whitespace to single spaces
            input = input.trim() ? input : ""; // Don't search if it's only whitespace
            gQuery = input;
            return input;
        },
        resultItem: {
            highlight: true
        },
        resultsList: {
            maxResults: MAX_RESULTS,
            element: (list,data) => {
                let listLength = "";
                if (data.results.length < data.matches.length || gItemMatchingCallbackRef)
                    listLength = String(data.matches.length);
                if (gItemMatchingCallbackRef) // We are in process of calculating the whole list
                    listLength += "+";
                if (listLength) {
                    const info = document.createElement("p");
                    info.innerHTML = `Showing <b>${data.results.length}</b> out of <b id="autocomplete-total-items">${listLength}</b> results`;
                    list.append(info);
                }
                try {
                    lucide.createIcons(lucide.icons); // Render the icons after building the list
                } catch (err) { }
            }
        },
        events: {
            input: {
                selection: (event) => {
                    const selection = event.detail.selection.value;

                    debugLog("Selected",selection.icon,selection.long);
                    let inputBox = document.getElementById('floating-search-input');
                    inputBox.blur();
                    inputBox.value = "";
                    gQuery = "";
                    if (gSearchWithinQuery) {
                        addFilter(gSearchWithinQuery,selection.chip);
                        openLocalPage("search/Advanced-search.html",String(gSearchWithinQuery));
                        gSearchWithinQuery = null;
                    } else
                        openLocalPage(selection.link);
                },
            }
        },
        resultItem: {
            element: (item, data) => {
                // Modify Results Item Style
                // item.style = "display: flex;";
                // Modify Results Item Content
                let matchText = data.key === "number" ? data.value.short : data.match;
                let icon = data.value.icon;
                let dimmed = false;
                if (icon && !icon.match("<"))
                    icon = `<i data-lucide="${icon}"></i>`
                let suffix = data.value.suffix;
                if (gSearchWithinQuery) {
                    let matchingExcerpts = excerptsMatchingItem(data.value);
                    suffix += ` (${matchingExcerpts})`;
                    if (gSearchWithinExcerpts && (matchingExcerpts === gSearchWithinExcerpts.length))
                        dimmed = true;
                } else {
                    if (data.value.excerptCount)
                        suffix += ` (${data.value.excerptCount})`;
                }
                let entryHtml = `${icon} ${matchText} ${suffix}`;
                if (dimmed)
                    entryHtml = `<span class="dimmed">${entryHtml}</span>`
                item.innerHTML = entryHtml;
            },
            highlight: true,
        }
    });
}

function setupOptionalSuttaRefs() {
    // Link suttas to local pages when the alt/option key is pressed
    // and to https://suttacentral.express/ when the shift key is pressed.

    document.addEventListener("click", function(event) {
        if (event.altKey || event.ctrlKey) {
            let hyperlink = event.target;
            while (hyperlink && !hyperlink.href) {
                hyperlink = hyperlink.parentElement;
            }
            if (hyperlink) {
                if (event.altKey) {
                    let suttaPage = hyperlink.dataset.altHref;
                    if (suttaPage) {
                        event.preventDefault();
                        suttaPage = suttaPage.replace("../","");
                        debugLog("Opening sutta page:",suttaPage);
                        let parts = suttaPage.split("#");
                        openLocalPage(parts[0],"",parts.length > 1 ? parts[1] : "");
                    }
                } else {
                    event.preventDefault();
                    window.open(hyperlink.href.replace("https://suttacentral.net/","https://suttacentral.express/"),"_blank");
                }
            }
        }
    });
}

function displayExcerptCount(itemsFound) {
    // Display the number of excerpts found in the floating search bar

    let text = itemsFound ? `${itemsFound} excerpt${itemsFound > 1 ? "s" : ""}` : "";
    document.getElementById("found-count").innerText = text;
}

function countFoundExcerpts() {
    let query = document.getElementById("floating-search-input").value.trim();
    if (!query) {
        displayExcerptCount(0);
        let spinner = document.getElementById("progress-spinner");
        spinner.style.display = "none"; // Hide the spinner when there is no search query.
        return;
    }
    try {
        let searchGroups = new SearchQuery(query);
        gSearchers["x"].search(searchGroups,gSearchWithinExcerpts ? gSearchWithinExcerpts : gSearchers["x"].items);
        displayExcerptCount(gSearchers["x"].foundItems.length);
    } catch (err) {
        displayExcerptCount(0);
    }
}

function moveToNewParent(oldParent,newParent) {
    // Move all DOM items from oldParent to newParent
    while (oldParent.childNodes.length > 0) {
       newParent.appendChild(oldParent.childNodes[0]);
    }
}

let gMenuFloating = false;
let gLastScrollY = window.scrollY;
let gLastPage = location.href;
let gScrollDirection = 0; // positive = down, negative = up

function closeFloatingSubmenus() {
    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        dropdownMenu.classList.remove('menu-open');
    });
}

function floatMenus(shouldFloat,shouldShow) {
    // If shouldFloat, move the menu to the floating menu div
    let fixedMenu = document.getElementById("header-content");
    let floatingMenu = document.getElementById("floating-header");
    if (shouldFloat === null)
        shouldFloat = gMenuFloating;
    if (shouldFloat & shouldShow) {
        if (!floatingMenu.classList.contains("active")) {
            document.querySelector("nav.main-nav").classList.remove("active");
            fixedMenu.style.minHeight = "";
            floatingMenu.classList.add("active");
        }
    } else if (floatingMenu.classList.contains("active")) {
        closeFloatingSubmenus();
        floatingMenu.classList.remove("active");
    }

    if (shouldFloat === gMenuFloating)
        return;

    closeFloatingSubmenus();
    if (shouldFloat && fixedMenu.querySelector(".main-nav.active"))
        fixedMenu.style.minHeight = `${fixedMenu.getBoundingClientRect().height}px`; 
            // Keep occupying the space of the open menu
    else
        fixedMenu.style.minHeight = "";

    let oldLocation = shouldFloat ? fixedMenu : floatingMenu;
    let newLocation = shouldFloat ? floatingMenu : fixedMenu;
    moveToNewParent(oldLocation,newLocation);

    gNavBar = newLocation;
    gMenuFloating = shouldFloat;
}

function bottomOfHeader() {
    // Return the Y coordinate of the bottom of the header in the viewport
    let header = document.getElementById("header-content");
    let headerBottom = header.getBoundingClientRect().bottom;
    for (let menu of header.querySelectorAll(".dropdown.menu-open .dropdown-content")) {
        headerBottom = Math.max(headerBottom,menu.getBoundingClientRect().bottom);
    }
    return headerBottom;
}

function scrollEndHandler(event) {
    // Float the menu only if we have scrolled down past the threshold on the same page we began with
    if ((bottomOfHeader() < 0) && (gLastPage === location.href)) {
        let searchBarShowing = document.querySelector(".floating-search").classList.contains('active');
        let floatingMenuShowing = document.getElementById("floating-header").classList.contains('active');
        floatMenus(true,(gScrollDirection < 0) && (!searchBarShowing || floatingMenuShowing));
        debugLog("Floating menu");
    } else {
        floatMenus(false,false);
        debugLog("Fixed menu.");
    }
    gLastScrollY = window.scrollY;
    gLastPage = location.href;
    gScrollDirection = 0;
}

if ("onscrollend" in window) {
    window.addEventListener("scrollend",scrollEndHandler);
} else {
    let timeOutID = 0;
    window.addEventListener("scroll",(event) => {
        if (timeOutID)
            window.clearTimeout(timeOutID);
        timeOutID = window.setTimeout(() => {
            scrollEndHandler();
        },500);
    });
}

window.addEventListener("scroll", (event) => {
    let newScrollY = window.scrollY;
    if (newScrollY - gLastScrollY)
        gScrollDirection = newScrollY - gLastScrollY;
    gLastScrollY = newScrollY;

    if ((gScrollDirection > 0) && gMenuFloating)
        floatMenus(true,false);
    if (bottomOfHeader() > 0)
        floatMenus(false,false);
});

let gMeditationTimer = null;
document.addEventListener('DOMContentLoaded', () => {
    // Called only once after pages/index.html DOM is loaded
    debugLog("DOMContentLoaded event");
	configureLinks(document.querySelector("header"),"index.html");
	configureLinks(document.querySelector("footer"),"index.html");

    setupNavMenuTriggers();
    gMeditationTimer = new MeditationTimer();

    // Display the number of excerpts found with this search
    document.getElementById("floating-search-input").addEventListener("input",countFoundExcerpts);

    setupOptionalSuttaRefs();

    if (DEBUG) { // Configure keyboard shortcuts to change homepage featured excerpt
        document.addEventListener("keydown", function(event) {
            let featuredExcerptContainer = document.getElementById("todays-excerpt");
            if (!featuredExcerptContainer)
                return;
            if ((event.key === "ArrowLeft") || (event.key === "ArrowRight")) {
                let offset = event.shiftKey ? 30 : 1;
                if (event.key === "ArrowLeft")
                    gDebugDateOffset -= offset;
                else
                    gDebugDateOffset += offset;
                let debugDate = new Date();
                debugDate.setDate(debugDate.getDate() + gDebugDateOffset);
                initializeTodaysExcerpt(debugDate);
                featuredExcerptContainer.innerHTML = gTodaysHolidayHtml + 
                    gHomepageDatabase.excerpts[gFeaturedDatabase.calendar[gTodaysExcerpt]];
                configureLinks(featuredExcerptContainer,"search/homepage.html");
                updateDate(debugDate);
            }
        });
    }
});