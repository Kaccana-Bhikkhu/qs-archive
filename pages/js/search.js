import {configureLinks,frameSearch,setFrameSearch} from './frame.js';
import { loadToggleView } from './toggle-view.js';

const TEXT_DELIMITERS = "][{}<>^";
const METADATA_DELIMITERS = "#&@";
const METADATA_SEPERATOR = "|"
const SPECIAL_SEARCH_CHARS = TEXT_DELIMITERS + METADATA_DELIMITERS + "()";

const HAS_METADATADELIMITERS = new RegExp(`.*[${METADATA_DELIMITERS}]`);

const PALI_DIACRITICS = {
    "a":"ā","i":"ī","u":"ū",
    "d":"ḍ","l":"ḷ","t":"ṭ",
    "n":"ñṇṅ","m":"ṁṃ",
    "'": '‘’"“”'                // A single quote matches all types of quotes
};

let PALI_DIACRITIC_MATCH_ALL = {};
Object.keys(PALI_DIACRITICS).forEach((letter) => {
    PALI_DIACRITIC_MATCH_ALL[letter] = `[${letter}${PALI_DIACRITICS[letter]}]`;
});

const DEBUG = false;

export function regExpEscape(literal_string) {
    return literal_string.replace(/[-[\]{}()*+!<>=:?.\/\\^$|#\s,]/g, '\\$&');
}

const ESCAPED_HTML_CHARS = regExpEscape(SPECIAL_SEARCH_CHARS);
const MATCH_END_DELIMITERS = new RegExp(`^\\\\[${regExpEscape(TEXT_DELIMITERS)}]+|\\\\[${regExpEscape(TEXT_DELIMITERS)}]+$`,"g");

function capitalizeFirstLetter(val) {
    return String(val).charAt(0).toUpperCase() + String(val).slice(1);
}

function nbsp(count) {
    return "&nbsp;".repeat(count);
}

function modulus(numerator,denominator) {
    return ((numerator % denominator) + denominator) % denominator;
}

export async function loadSearchDatabase() {
    if (!gSearchDatabase) {
        await fetch('./assets/SearchDatabase.json')
        .then((response) => response.json())
        .then((json) => {
            gSearchDatabase = json; 
            debugLog("Loaded search database.");
            for (let code in gSearchers) {
                gSearchers[code].loadItemsFomDatabase(gSearchDatabase)
            }
        });
    }
}

export async function loadSearchPage() {
    // Called when a search page is loaded. Load the database, configure the search button,
    // fill the search bar with the URL query string and run a search.

    let searchButtonsFound = 0;
    for (let searchCode in gSearchers) {
        let searchButton = document.getElementById(`search-${searchCode}-button`);
        if (searchButton) {
            searchButton.addEventListener("click",function(event) {
                searchButtonClick(searchCode);
                event.preventDefault();
            });
            searchButtonsFound += 1;
        }
    }

    if (!searchButtonsFound)
        return;

    let params = frameSearch();
    let query = params.has("q") ? decodeURIComponent(params.get("q")) : "";
    if (!query)
        document.getElementById("search-text").focus();

    await loadSearchDatabase();

    searchFromURL();
}

function matchEnclosedText(separators,dontMatchAfterSpace) {
    // Return a regex string that matches the contents between separators.
    // Separators is a 2-character string like '{}'
    // Match all characters excerpt the end character until a space is encountered.
    // If any characters in dontMatchAfterSpace are encountered, match only up until the space.
    // If the end character is encountered, match it.

    let escapedStart = regExpEscape(separators[0]);
    let escapedEnd = regExpEscape(separators[1]);
    
    return [escapedStart,
        `[^${escapedEnd} ]*`,
        "(?:",
            `[^${escapedEnd + regExpEscape(dontMatchAfterSpace)}]*`,
            escapedEnd,
        ")"
    ].join("");
}

function substituteWildcards(regExpString) {
    // Convert the following wildcards to RegExp strings:
    // * Match any or no characters
    // _ Match exactly one character
    // $ Match word boundaries

    // Strip off leading and trailing * and $. The innermost symbol determines whether to match a word boundary.
    let bounded = regExpEscape(regExpString.replace(/^[$*]+/,"").replace(/[$*]+$/,""));
    if (regExpString.match(/^[$*]*/)[0].endsWith("$"))
        bounded = "\\b" + bounded;
    if (regExpString.match(/[$*]*$/)[0].startsWith("$"))
    bounded += "\\b";

    // Replace inner * and _ and $ with appropriate operators.
    return bounded.replaceAll("\\*",`[^${ESCAPED_HTML_CHARS}]*?`).replaceAll("_",`[^${ESCAPED_HTML_CHARS}]`).replaceAll("\\$","\\b");
}

class SearchBase {
    // Abstract search class; matches either nothing or everything depending on negate
    negate = false; // This flag negates the search

    matchesBlob(blob) { // Does this search term match a given blob?
        return negate; 
    }

    matchesItem(item) { // Does this search group match an item?
        if (this.negate) {
            debugLog("negate")
        }
        for (const blob of item.blobs) {
            if (this.matchesBlob(blob))
                return !this.negate;
        }
        return this.negate;
    }

    filterItems(items) { // Return an array containing items that match this group
        let result = [];
        for (const item of items) {
            if (this.matchesItem(item))
                result.push(item)
        }
        return result;
    }
}

// A class to parse and match a single term in a search query
class SearchTerm extends SearchBase {
    matcher; // A RegEx created from searchElement
    matchesMetadata = false; // Does this search term apply to metadata?
    boldTextMatcher = ""; // A RegEx string used to highlight this term when displaying results

    constructor(searchElement) {
        // Create a searchTerm from an element found by parseQuery.
        // Also create boldTextMatcher to display the match in bold.
        super();

        this.matchesMetadata = HAS_METADATADELIMITERS.test(searchElement);

        this.negate = searchElement.startsWith("!");
        searchElement = searchElement.replace(/^!/,"");

        if (/^[0-9]+$/.test(searchElement)) // Enclose bare numbers in quotes so 7 does not match 37
            searchElement = '"' + searchElement + '"'

        let qTagMatch = false;
        let aTagMatch = false;
        if (/\]\/\/$/.test(searchElement)) { // Does this query match qTags only?
            searchElement = searchElement.replace(/\/*$/,"");
            qTagMatch = true;
        }
        if (/^\/\/\[/.test(searchElement)) { // Does this query match aTags only?
            searchElement = searchElement.replace(/^\/*/,"");
            aTagMatch = true;
        }
        
        let unwrapped = searchElement;
        switch (searchElement[0]) {
            case '"': // Items in quotes must match on word boundaries.
                unwrapped = "$" + searchElement.replace(/^"+/,'').replace(/"+$/,'') + "$";
                break;
        }

        // Replace inner * and $ with appropriate operators.
        let escaped = substituteWildcards(unwrapped);
        let finalRegEx = escaped;
        if (qTagMatch) {
            finalRegEx += "(?=.*//)";
        }
        if (aTagMatch) {
            finalRegEx += "(?!.*//)";
        }
        debugLog("searchElement:",searchElement,finalRegEx);
        this.matcher = new RegExp(finalRegEx);

        if (this.matchesMetadata)
            return; // Don't apply boldface to metadata searches

        // Start processing again to create RegExps for bold text
        let boldItem = escaped;
        debugLog("boldItem before:",boldItem);
        boldItem = boldItem.replaceAll(MATCH_END_DELIMITERS,"");

        for (const letter in PALI_DIACRITIC_MATCH_ALL) { // 
            boldItem = boldItem.replaceAll(letter,PALI_DIACRITIC_MATCH_ALL[letter]);
        }

        debugLog("boldItem after:",boldItem);
        this.boldTextMatcher = boldItem;
    }

    matchesBlob(blob) { // Does this search term match a given blob?
        if (!this.matchesMetadata) {
            blob = blob.split(METADATA_SEPERATOR)[0];
        }
        return this.matcher.test(blob);
    }
}

class SearchGroup extends SearchBase {
    // An array of searchTerms. Subclasses define different operations (and, or, single item match)
    terms = []; // An array of searchBase items

    constructor() {
        super()
    }

    addTerm(searchString) {
        this.terms.push(new SearchTerm(searchString));
    }

    matchesItem(item) { // Does this search group match an item?
        for (const blob of item.blobs) {
            let allTermsMatch = true;
            for (const term of this.terms) {
                if (!term.matchesBlob(blob))
                    allTermsMatch = false;
            }
            if (allTermsMatch)
                return true;
        }
        return false;
    }
}

class SearchAnd extends SearchGroup {
    // This class matches an item only if all of its terms match the item.
    matchesItem(item) { // Does this search group match an item?
        for (const term of this.terms) {
            if (!term.matchesItem(item))
                return self.negate;
        }
        return !self.negate;
    }
}

class SingleItemSearch extends SearchGroup {
    // This class matches an item only if all of its terms match a single blob within that item.
    // This can be used to match excerpts containing stories with tag [Animal]
    // as distinct from excerpts containing a story annotation and the tag [Animal] applied elsewhere.
    matchesItem(item) { // Does this search group match an item?
        for (const blob of item.blobs) {
            let allTermsMatch = true;
            for (const term of this.terms) {
                if (!term.matchesBlob(blob))
                    allTermsMatch = false;
            }
            if (allTermsMatch)
                return true;
        }
        return false;
    }
}

export class SearchQuery {
    // An array of searchGroups that describes an entire search query
    groups = []; // An array of searchGroups representing the query
    boldTextRegex; // A regular expression matching found texts which should be displayed in bold

    constructor(queryText) {
        // Construct a search query by parsing queryText into search groups containing search terms.
        // Search groups are specified by enclosure within parenthesis.
        // Each excerpt must match all search groups.
        // Search keys within a search group must be matched within the same blob.
        // So (#Read Pasanno}) matches only kind 'Reading' or 'Read by' with teacher ending with Pasanno
        
        queryText = queryText.toLowerCase();
        queryText = queryText.normalize("NFD").replace(/[\u0300-\u036f]/g, ""); // https://stackoverflow.com/questions/990904/remove-accents-diacritics-in-a-string-in-javascript
    
        // 1. Build a regex to parse queryText into items
        let parts = [
            matchEnclosedText('""',''),
                // Match text enclosed in quotes
            matchEnclosedText('{}',SPECIAL_SEARCH_CHARS),
                // Match teachers enclosed in braces
            "/*" + matchEnclosedText('[]',SPECIAL_SEARCH_CHARS) + "\\+?/*",
                // Match tags enclosed in brackets
                // Match the forms: [tag]// (qTag only), //[tag] (aTag only), [tag]+ (fTag only)
            "[^ ]+"
                // Match everything else until we encounter a space
        ];
        parts = parts.map((s) => "!?" + s); // Add an optional ! (negation) to these parts
        let partsSearch = "\\s*(" + parts.join("|") + ")"
        debugLog(partsSearch);
        partsSearch = new RegExp(partsSearch,"g");
    
        // 2. Create items and groups from the found parts
        for (let match of queryText.matchAll(partsSearch)) {
            let group = new SearchAnd();
            group.addTerm(match[1].trim());
            this.groups.push(group);
        }

        // 3. Construct the regex to match bold text.
        let textMatchItems = [];
        for (const group of this.groups) {
            for (const term of group.terms) {
                if (term.boldTextMatcher)
                    textMatchItems.push(term.boldTextMatcher);
            }
        }
        debugLog("textMatchItems",textMatchItems);
        if (textMatchItems.length > 0)
            this.boldTextRegex = new RegExp(`(${textMatchItems.join("|")})(?![^<]*\>)`,"gi");
                // Negative lookahead assertion to avoid modifying html tags.
        else
            this.boldTextRegex = /^a\ba/ // a RegEx that doesn't match anything
        debugLog(this.boldTextRegex)
    }

    filterItems(items) { // Return an array containing items that match all groups in this query
        let found = items;
        for (const group of this.groups) {
            found = group.filterItems(found);
        }
        return found;
    }

    displayMatchesInBold(string) { // Add <b> and </b> tags to string to display matches in bold
       return string.replace(this.boldTextRegex,"<b>$&</b>")
    }
}

export function renderExcerpts(excerpts,searcher,sessionHeaders) {
    // Convert a list of excerpts to html code by concatenating their html attributes
    // Display strings in boldTextItems in bold.

    let bits = [];
    let lastSession = null;

    for (const x of excerpts) {
        if (x.session != lastSession) {
            bits.push(sessionHeaders[x.session]);
            lastSession = x.session;
        }
        bits.push(searcher.displayMatchesInBold(x.html));
        bits.push("<hr>");
    }
    return bits.join("\n");
}

function clearSearchResults(message) {
    // Called when the search query is blank
    let messageFrame = document.getElementById('message');
    let instructionsFrame = document.getElementById('instructions');
    let resultsFrame = document.getElementById('results');

    instructionsFrame.style.display = "block";
    resultsFrame.innerHTML = "";

    if (message) {
        messageFrame.innerHTML = message;
        messageFrame.style.display = "block";
    } else
        messageFrame.style.display = "none";
}

function displaySearchResults(message,searchResults) {
    // Display the seach results in the various html frames

    let messageFrame = document.getElementById('message');
    let instructionsFrame = document.getElementById('instructions');
    let resultsFrame = document.getElementById('results');

    instructionsFrame.style.display = "none";

    resultsFrame.innerHTML = searchResults;
    configureLinks(resultsFrame,location.hash.slice(1));
    loadToggleView(resultsFrame);

    if (message) {
        messageFrame.innerHTML = message;
        messageFrame.style.display = "block";
    } else
        messageFrame.style.display = "none";
}

class Searcher {
    code; // a one-letter code to identify the search.
    name; // the name of the search, e.g. "Tag"
    plural; // the plural name of the search.
    prefix = "<p>"; // html prefix of each search result.
    suffix = "</p>"; // hmtl suffix of each search result.
    separator = ""; // the html code to separate each displayed search result.
    itemsPerPage = null; // The number of items to display per page.
        // itemsPerPage = null displays all items regardless of length.
        // The base class Searcher displays only one page.
    divClass = "listing"; // Enlcose the search results in a <div> tag with this class.
    multiSearchHeading = false; // Should we display a heading for use with MultiSearcher?
    items = []; // A list of items of the form:
        // database[n].blobs: an array of search blobs to match
        // database[n].html: the html code to display this item when found
    query = null; // A searchQuery object describing the search
    foundItems = []; // The items we have found.
    multiSearcher = null; // Set to the MultiSearcher object we are part of.
    
    constructor(code,name) {
        // Configure a search with a given code and name
        this.code = code;
        this.name = name;
        this.plural = this.name + "s";
    }

    loadItemsFomDatabase(database) {
        // Called after SearchDatabase.json is loaded to prepare for searching
        this.items = database.searches[this.code].items;
    }

    search(searchQuery) {
        debugLog(this.name,"search.");
        this.query = searchQuery
        this.foundItems = searchQuery.filterItems(this.items);
    }

    renderItems(startItem = 0,endItem = null) {
        // Convert a list of items to html code by concatenating their html attributes
        // Display strings in boldTextItems in bold.

        if (endItem == null)
            endItem = undefined;
        let rendered = [];
        for (let item of this.foundItems.slice(startItem,endItem)) {
            rendered.push(this.prefix + this.query.displayMatchesInBold(item.html) + this.suffix);
        }

        return rendered.join(this.separator);
    }

    htmlSearchResults() {
        // Return an html string containing the search results.
        // Returns an empty string if the search didn't find anything.
        if (this.foundItems.length > 0) {
            let items = this.renderItems(0,this.itemsPerPage);
            let heading = "";
            if (this.multiSearchHeading) { // Match the formatting of TruncatedSearcher
                heading = `\n<h3>${this.foundItemsHeader()}</h3>`;
                items = `<div id="results-${this.code}.b">\n` + items + `\n</div>`
            }
            return `<div class="${this.divClass}" id="results-${this.code}">${heading}\n${items}\n</div>`;
        } else
            return "";
    }

    foundItemsString() {
        // Returns a string describing the found items in th form "27 tags"
        // Returns "" if no items were found.
        if (this.foundItems.length > 0)
            return `${this.foundItems.length} ${this.foundItems.length > 1 ? this.plural : this.name}`;
        else
            return "";
    }

    foundItemsHeader() {
        // Returns a string describing the found items in the form "Tags (27):"
        // Returns "" if no items were found.

        if (this.foundItems.length > 0)
            return `${capitalizeFirstLetter(this.plural)} (${this.foundItems.length}):`;
        else
            return "";
    }

    showResults(message = "") {
        // Display the results of this search in the main window.
        // message is an optional message to display.
        
        if (this.foundItems.length > 0) {
            message += `Found ${this.foundItemsString()}`;
            if (this.itemsPerPage && this.foundItems.length > this.itemsPerPage)
                message += `. Showing only the first ${this.itemsPerPage}:`;
            else
                message += ":"

            displaySearchResults(message,this.htmlSearchResults());
            this.configureResultsFrame(document.getElementById('results'));
        } else {
            message += `No ${this.plural} found.`
            clearSearchResults(message);
        }
    }

    configureResultsFrame(frame) {
        // Called to configure javascript links, etc. within the search results frame.
        // There's nothing to do in the Searcher base class.
    }
}

class TruncatedSearcher extends Searcher {
    // A Searcher that shows only a few results to begin with followed by "Show all...".
    // The whole search can be hidden using a toggle-view object.
    // Displays its own header e.g. "Teachers (2):", so it's intended to be used with MultiSearcher.

    truncateAt; // Truncate the initial view if there are more than this many items

    constructor(code,name,truncateAt) {
        super(code,name);
        this.truncateAt = truncateAt;
    }

    htmlSearchResults() {
        if (this.foundItems.length == 0)
            return "";

        let resultsId = `results-${this.code}`;

        let firstItems = "";
        let moreItems = "";
        if (this.foundItems.length > this.truncateAt) {
            firstItems = this.renderItems(0,this.truncateAt - 1);
            let moreItemsBody = this.renderItems(this.truncateAt - 1);
            moreItems = ` 
            <a class="toggle-view hide-self" id="${resultsId}-more" href="#"><i>Show all ${this.foundItems.length}...</i></a>
            <div id="${resultsId}-more.b" style="display:none;">
            ${moreItemsBody}
            </div>
            `;
        } else {
            firstItems = this.renderItems();
        }
        
        return ` 
        <div class="${this.divClass}" id="results-${this.code}">
        <h3><a><i class="fa fa-minus-square toggle-view" id="${resultsId}"></i></a> ${this.foundItemsHeader()}</h3>
        <div id="${resultsId}.b">
        ${firstItems} 
        ${moreItems}
        </div>
        </div>
        `;
    }
}

class PagedSearcher extends Searcher {
    // Extends Searcher to show multiple pages instead of just one.

    constructor(code,name,itemsPerPage) {
        super(code,name);
        this.itemsPerPage = itemsPerPage;
    }

    htmlSearchResults() {
        // Provide a multi-page view of these excerpts.
        if (!this.foundItems.length)
            return "";

        let pageCount = Math.ceil(this.foundItems.length / this.itemsPerPage);
        if (pageCount == 1) {
            return super.htmlSearchResults();
        }

        let heading = "";
        if (this.multiSearchHeading)
            heading = `\n<h3>${this.foundItemsHeader()}</h3>`;

        const pageNumberParam = `${this.code}Page`;
        let params = frameSearch(location.hash);
        let currentPage = 1;
        if (params.has(pageNumberParam))
            currentPage = Number(params.get(pageNumberParam));

        let pageMenu = "";
        if (pageCount > 0) {
            let pageNumbers = [...Array(pageCount).keys()].map((n) => (n+1));
            let pageLinks = pageNumbers.map((n) => {
                let newParams = frameSearch(location.hash);
                newParams.set(pageNumberParam,String(n));
                return `<a href="${setFrameSearch(newParams,location)}"${n == currentPage ? 'class="active"' : ''}>${n}</a>`;
            });

            pageMenu = `\n<p class="page-list">Page:&emsp;${pageLinks.join("&emsp;")}</p>`;
        }

        let rendered = this.renderItems((currentPage - 1) * this.itemsPerPage,currentPage * this.itemsPerPage);
        return `<div class="${this.divClass}" id="results-${this.code}">${heading}${pageMenu}\n${rendered}\n${pageMenu}</div>`;
    }

    showResults(message = "") {
        // Display the results of this search in the main window.
        // message is an optional message to display.
        
        if (this.foundItems.length > 0) {
            message += `Found ${this.foundItemsString()}:`;
            displaySearchResults(message,this.htmlSearchResults());
            this.configureResultsFrame(document.getElementById('results'));
        } else {
            message += `No ${this.plural} found.`
            clearSearchResults(message);
        }
    }

    configureResultsFrame(resultsFrame) {
        // Set click listeners to the page menus so we don't have to redo the search.
        let secondMenu = false;
        for (let menu of resultsFrame.getElementsByClassName("page-list")) {
            for (let item of menu.getElementsByTagName("a")) {
                item.scrollToTop = secondMenu;
                item.addEventListener("click", (event) => {
                    let pageNumber = event.target.innerHTML;
                    let params = frameSearch(location.hash);
                    params.set(`${this.code}Page`,pageNumber);
                    setFrameSearch(params);
                    if (this.multiSearcher)
                        this.multiSearcher.showResults();
                    else
                        this.showResults();
                    if (event.target.scrollToTop) {
                        let resultsFrame = document.getElementById(`results-${this.code}`);
                        resultsFrame.scrollIntoView();
                    }
                    event.preventDefault();
                });
            }
            secondMenu = true;
        }
    }
}

export class ExcerptSearcher extends PagedSearcher {
    // Specialised search object for excerpts
    code = "x"; // a one-letter code to identify the search.
    name = "excerpt"; // the name of the search, e.g. "Tag"
    plural = "excerpts"; // the plural name of the search.
    prefix = ""; // html prefix of each search result.
    suffix = ""; // hmtl suffix of each search result.
    separator = "<hr>"; // the html code to separate each displayed search result.
    itemsPerPage = 100; // The number of items to display per page.
        // itemsPerPage = 0 displays all items regardless of length.
        // The base class Searcher displays only one page.
    divClass = ""; // Enlcose the search results in a <div> tag with this class.
    sessionHeader = {};   // Contains rendered headers for each session.

    loadItemsFomDatabase(database) {
        // Called after SearchDatabase.json is loaded to prepare for searching
        super.loadItemsFomDatabase(database);
        this.sessionHeader = database.searches[this.code].sessionHeader;
    }

    renderItems(startItem = 0,endItem = null) {
        // Convert a list of excerpts to html code by concatenating their html attributes and
        // inserting session headers where needed.
        // Display strings in boldTextItems in bold.

        if (endItem == null)
            endItem = undefined;

        let bits = [];
        let lastSession = null;

        if (this.multiSearchHeading && (this.foundItems.length <= this.itemsPerPage))
            bits.push("<br/>");

        for (const x of this.foundItems.slice(startItem,endItem)) {
            if (x.session != lastSession) {
                bits.push(this.sessionHeader[x.session]);
                lastSession = x.session;
            }
            bits.push(this.query.displayMatchesInBold(x.html));
            bits.push(this.separator);
        }
        return bits.join("\n");
    }
}

class MultiSearcher {
    // Conduct multiple searches with the same search query
    // Uses duck typing to behave like a Searcher without inheriting from it.

    code; // a one-letter code to identify the search.
    separator = "<hr>"; // the html code to separate each displayed search.
    query = null; // a searchQuery object describing the search
    searches = []; // a list of Searcher objects describing what to search for

    constructor(code, ...searches) {
        this.code = code;
        this.searches = searches;
        for (let s of this.searches) {
            s.multiSearchHeading = true;
            s.multiSearcher = this;
        }
    }

    loadItemsFomDatabase(database) {
        for (let s of this.searches) {
            s.loadItemsFomDatabase(database);
        }
    }

    search(searchQuery) {
        debugLog("Multisearch.");
        this.query = searchQuery;
        for (let s of this.searches) {
            s.search(searchQuery);
        }
    }

    successfulSearches() {
        // Returns the number of searches that found anything.
        let successful = 0;
        for (let s of this.searches) {
            if (s.foundItems.length > 0)
                successful += 1;
        }
        return successful;
    }

    showResults(message = "") {
        // Show the results of all our searches combined.
        // message is an optional message to display.
        
        if (this.successfulSearches()) {
            let searchMessages = this.searches.map((s) => s.foundItemsString());
            searchMessages = searchMessages.filter((s) => s.length > 0);
            if (searchMessages.length > 2)
                message += `Found ${searchMessages.slice(0,-1).join(", ")}, and ${searchMessages[searchMessages.length - 1]}.`;
            else if (searchMessages.length > 1)
                message += `Found ${searchMessages[0]} and ${searchMessages[1]}.`;
            else
                message += `Found ${searchMessages[0]}.`;

            let searchResults = this.searches.map((s) => s.htmlSearchResults());
            searchResults = searchResults.filter((s) => s.length > 0);
            displaySearchResults(message,'<hr style="margin-top: 0px;">' + searchResults.join(this.separator));

            for (let s of this.searches) {
                let resultFrame = document.getElementById(`results-${s.code}`);
                if (resultFrame)
                    s.configureResultsFrame(resultFrame);
            }
        } else {
            message += `No items found.`
            clearSearchResults(message);
        }
    }
}

function searchFromURL() {
    // Find excerpts matching the search query from the page URL.
    if (!gSearchDatabase) {
        debugLog("Error: database not loaded.");
        return;
    }

    let params = frameSearch();
    let query = params.has("q") ? decodeURIComponent(params.get("q")) : "";
    let searchKind = params.has("search") ? decodeURIComponent(params.get("search")) : "all";

    debugLog("Called searchFromURL. Query:",query);
    frame.querySelector('#search-text').value = query;

    if (!query.trim()) {
        clearSearchResults();
        return;
    }

    let searchGroups = new SearchQuery(query);
    debugLog(searchGroups);

    gSearchers[searchKind].search(searchGroups);
    gSearchers[searchKind].showResults();
}

function searchButtonClick(searchKind) {
    // Read the search bar text, push the updated URL to history, and run a search.
    let searchInput = frame.querySelector('#search-text');
    searchInput.blur();
    let query = searchInput.value;
    debugLog("Called runFromURLSearch. Query:",query,"Kind:",searchKind);

    let search = new URLSearchParams({q : encodeURIComponent(query),search : searchKind});
    history.pushState({},"",location.href); // First push a new history frame
    setFrameSearch(search); // Then replace the history with the search query

    searchFromURL();
}

let gSearchDatabase = null; // The global search database, loaded from assets/SearchDatabase.json
export let gSearchers = { // A dictionary of searchers by item code
    "x": new ExcerptSearcher(),
    "multi-tag": new MultiSearcher("multi-tag",
        new Searcher("k","key topic"),
        new Searcher("b","subtopic"),
        new Searcher("g","tag")
    ),
    "t": new Searcher("t","teacher"),
    "e": new Searcher("e","event"),
    "all": new MultiSearcher("all",
        new TruncatedSearcher("k","key topic",3),
        new TruncatedSearcher("b","subtopic",5),
        new TruncatedSearcher("g","tag",5),
        new TruncatedSearcher("t","teacher",5),
        new TruncatedSearcher("e","event",3),
        new ExcerptSearcher()
    )
};
