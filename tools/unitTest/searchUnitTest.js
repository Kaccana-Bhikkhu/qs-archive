import {SearchQuery,ExcerptSearcher} from '../../pages/js/search.js';

let gDatabase = null;
let gSearcher = null;
let gTestsCompleted = 0;
let gFailures = 0;

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

function unitTest(queryString,expectedResultCount,description) {
    // Search excerpts using query. 
    // It will find expectedResultsCount if everything is working.
    // Returns an html string. If successful this is a simple message.
    // If the test fails, it is the list of all excerpts found.

    let searchGroups = new SearchQuery(queryString);
    gSearcher.search(searchGroups);

    gTestsCompleted++;

    let output = "";
    if (gSearcher.foundItems.length === expectedResultCount) {
        output = `<b>${gTestsCompleted}. Passed.</b> ${description}: expected and found ${gSearcher.foundItems.length} excerpts.`
    } else {
        let processedQuery = String(searchGroups.searcher);
        output = `<b style="color:red;">${gTestsCompleted}. Failed.</b> ${description}: expected ${expectedResultCount} excerpts but found ${gSearcher.foundItems.length}.<br>`
        output += `Query text: ${queryString}<br>Processed query: ${processedQuery}<br>`
        output += gSearcher.renderItems();
        gFailures++;
    }
    showStatus(`${gTestsCompleted} tests completed. ${gFailures} failure(s).`);
    return output;
}

function runUnitTests() {
    let unitTestList = [
        ["Search functionality from Version 4.0:"],
        ["@UD2014-1",43,"All excerpts in UD2014-1"],
        ["@UD2014-1 {Ajahn",26,'All teachers beginning with "Ajahn"'],
        ["@UD2014-1 {Ajahn*}",26,'All teachers beginning with "Ajahn" (2)'],
        ["@UD2014-1 [*w*]",11,'All tags containing "w"'],
        ['@UD2014-1 Thai',2,'Thai'],
        ['@UD2014-1 Thai$',1,'Thai$'],
        ['@UD2014-1 "Thai"',1,'"Thai"'],
        ['@UD2014-1 "Thai*"',2,'"Thai*"'],
        ['@UD2014-1 "*Thai"',1,'"*Thai"'],
        ['@UD2014-1 #R',13,'Kinds starting with "R"'],
        ['@UD2014-1 "#R"',0,'Kinds only "R"'],
        ['@UD2014-1 [$K',6,'Tags starting with "K"'],
        ['@UD2014-1 [$K]',0,'Tags only "K"'],
        ['@UD2014-1 [M*t*]',11,'Tags containing "M" followed by "t"'],
        ['@UD2014-1 [S*l$*]',4,'Tags starting with "S" whose first word ends in "l"'],
        ['@UD2014-1 H_t',10,'H_t'],
        ['@UD2014-1 $H_s$',6,'$H_s$'],
        ['@UD2014-1 ^H',3,'Texts beginning with "H"'],
        ['@UD2014-1 .^',32,'Texts ending with "."'],
        ['@UD2014-1 ?^',13,'Texts ending with "?"'],
        ['@UD2014-1 #Question',13,'Questions'],
        ['@UD2014-1 "of good"',1,'"of good"'],
        ['@UD2014-1 of good',3,'of good without quotes'],
        ['Excerpt blob format 2.0:'],
        ['@UD2014-1 &References',9,'All references'],
        ['@UD2014-1 @s02',17,'All excerpts in Session 2'],
        ["Don't match metadata unless the query contains metadata chars:"],
        ['@UD2014-1 ud',7,'All excerpts containing text "ud"'],
        ["Search by number:"],
        ['@UD2014-1 2',1,'All excerpts containing the digit 2 alone'],
        ['@UD2014-1 "*2*"',6,'All excerpts containing any digit 2'],
        ['Search for fTags'],
        ['[Renunciation]+',3,'All [Renunciation] featured excerpts'],
        ['[Renunciation] +',9,'All featured excerpts with tag [Renunciation]'],
        ['Search for qTags and aTags'],
        ['@UD2014-1 [Merit]',9,'All excerpts with tag [Merit]'],
        ['@UD2014-1 [Merit]//',6,'All excerpts with qTag [Merit]'],
        ['@UD2014-1 //[Merit]',5,'All excerpts with aTag [Merit]'],
        ['Negation operator'],
        ['@UD2014-1 !death',2,'All excerpts that do not contain text "death"'],
        ['@UD2014-1 !',1,'All excerpts that contain "!"'],
        ['@UD2014-1 !!',42,'All excerpts that do not contain "!"'],
        ['Raw regular expressions'],
        ['@UD2014-1 `[0-9]{3}`',7,'All excerpts containing 3 digits in a row'],
        ['@UD2014-1 `a\\WB``',4,'All excerpts containing a followed by a non-word character followed by b'],
        ['Basic search groups'],
        ['@UD2014-1 |(Abhayagiri deceased)',5,'All excerpts containing "Abhayagiri" or "deceased"'],
        ['@UD2014-1 &(Abhayagiri deceased)',2,'All excerpts containing "Abhayagiri" and "deceased"'],
        ['@UD2014-1 ~(Abhayagiri deceased)',1,'All excerpts with a single item containing both "Abhayagiri" and "deceased"'],
        ['@UD2014-1 |(Abhayagiri deceased',5,'End parenthesis optional'],
        ['@UD2014-1 |(Abhayagiri deceased) west',3,'All excerpts containing "Abhayagiri" or "deceased" and "west"'],
        ['Negated search groups'],
        ['@UD2014-1 !(Abhayagiri deceased)',41,'All excerpts not containing "Abhayagiri" and "deceased"'],
        ['Complex search groups'],
        ['@UD2014-1 |(#verylong |(#veryshort father))',14,'Very short, very long, or contains "father"'],
        ['@UD2014-1 |(#verylong !&(death))',6,'Very long or does not contain "death"'],
        ['@UD2014-1 |(#verylong!&(death))',6,'Lookahead check for upcoming groups'],
    ];

    let results = ["All results are from searching UD2014-1 and tag [Renunciation].<br><br>"];
    let test = [];
    for (test of unitTestList) {
        if (test.length === 3)
            results.push(unitTest(test[0],test[1],test[2]) + "<br>");
        else
            results.push(`<br><h3>${test[0]}</h3>`)
    }

    showResults(results.join(""))

}

let startButton = document.getElementById("start-button");
startButton.onclick = () => { 
    loadDatabase().then(() => {
        runUnitTests();
    }) 
}
startButton.click()