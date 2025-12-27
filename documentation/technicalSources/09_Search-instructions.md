[Abhayagiri library](photo:Abhayagiri library.jpg)


The [search page](../search/Text-search.html?featured=&relevant=) allows one to search excerpts for text, tags, and teachers. One can narrow the search to specific kinds of teaching or events. Simple queries are easy, but more complex searches require an understanding of how the search engine works. Read this page only as far as you need to and then start searching.

The December 2024 release adds a "Search all" button which simultaneously searches key topics, subtopics, tags, teachers, events, and excerpts. Most of the documentation below still applies.

The June 2025 release adds a floating search bar to the main menu. Pressing '/' brings up the floating search bar from anywhere in a page.

## Searching for text

To search for text, tags, or teachers, simply type the text into the search bar.

By default the search finds text within words. To find whole words only, enclose the word in double quotes. To find a phrase, enclose the phrase in double quotes.

For example, searching for `Thai` finds both Thai and Thailand, but searching for `"Thai"` finds only Thai.

## Sorting by relevance

The December 2025 release attempts to prioritize the most useful search results. It does this by moving featured excerpts and excerpts which match text search terms in the most relevant places to the top of the results page. These features can be turned off by deselecting the appropriate check boxes on the search page. If neither check box is selected, excerpts are listed in chronological order.

## Searching for tags

Use brackets to search for excerpts tagged with specific tags:

Search for a single tag: `[Happiness]`

Search for all tags beginning with characters: `[History*]`

Search for all tags ending with characters: `[*Pasanno]`

Search for all tags containing characters: `[*Thai*]`

## Searching for teachers

Use braces to search for excerpts offered by specific teachers:

Search for a single teacher: `{Ajahn Dtun}`

Search for all teachers beginning with characters: `{Mae Chee*}`

Search for all teachers ending with characters: `{*Pasanno}`

## Searching for featured excerpts

To limit the search to featured excerpts, add ` +` after the search terms, e. g. `Thai +`.

## Searching by kind

To search for excerpts containing a specific kind of teaching, use a hash mark before or after the type of teaching:

Search for excepts containing a direct quote and the characters 'Thai': `#Quote Thai` 

Search for excepts containing an indirect quote and the characters 'Thai': `#IndirectQuote Thai`

## Searching by category

Excerpt kinds are grouped into categories as follows:

__`Questions`__: `Question`, `Response`, `FollowUp`
<br>
__`Stories`__: `Story`, `Recollection`
<br>
__`Teachings`__: `Teaching`, `Reflection`, `Simile`, `DhammaTalk`
<br>
__`Quotes`__: `Quote`, `IndirectQuote`
<br>
__`Meditations`__: `MeditationInstruction`, `GuidedMeditation`, `Chanting`
<br>
__`Readings`__: `Reading`
<br>
__`References`__: `Reference`, `Sutta`, `Vinaya`, `Commentary`
<br>
__`Other`__: `Comment`, `Discussion`, `Note`, `Summary`, `Other`
<br>
__`Attribution`__: `ReadBy`, `TranslatedBy`

Use an ampersand (&) before the category name to search for excerpts in that category.

Search for any quote containing the characters 'Thai': `&Quotes Thai`

## Searching by event

To search for excerpts from a specific event use the @ symbol before the event code. Event codes are of the form `Metta2008` or `UD2015-3` and contain a four-digit year. One can find event codes in the hyperlinks on the [Events page](../indexes/EventsBySeries.html). Since all events in a series begin with the same characters, one can search for excerpts from a particular series:

Search for Thanksgiving Retreats: `@TG`

Search for Winter Retreats: `@WR`

Search for Spirit Rock Daylongs: `@SRD`

Search for Upāsikā Days: `@UD`

Search for events from the year 2015: `@*2015`

## Boolean search operations

Boolean search operations can be used by grouping terms in operator-prefix notation: `X(term1 term2 term3 ...)`, where the operator `X` is one of the following:

__`|`__ Or: Only one term must match. <br>
__`&`__ And: All terms must match. <br>
__`~`__ Like And, but all terms must match in the same search blob (see [Advanced searching](#advanced-searching) below).

Thus `|([Mindfulness] [Right Mindfulness])` finds excerpts matching either of these tags and `~(#Comment# {Ajahn Pasanno})` finds comments made by Ajahn Pasanno but not excerpts in which Ajahn Pasanno responds to a comment made by someone else.

Search terms or groups preceeded by `!` are negated, e.g. `!Thai` finds all excerpts not containing the characters `Thai`, and `!|({Ajahn Pasanno} {Ajahn Amaro} {Ajahn Karunadhammo})` finds excerpts to which none of these teachers contributed.

## Advanced searching

To go beyond the recipies above, it is necessary to understand the search engine in  detail. The search engine converts excerpts and annotations into a series of blobs in which special characters are used to indicate tags, teachers, kinds, and events. For example, this excerpt:

![Example Excerpt](image:ExampleExcerpt.png)

is converted into these five blobs:

1. `^could you please explain about the death process...how quickly does rebirth occur?^{ajahn pasanno}[death]+[rebirth]//[recollection/death][delusion][self-identity view][recollection][impermanence][not-self][theravada][history/early buddhism][sutta][vajrayana][clinging][culture/thailand][chanting][goodwill][relinquishment][ceremony/ritual][kamma]|#question#verylong#&questions&@metta2008@s01@e3@`
2. `^chanting book p 55: five recollections; chanting book p 12: the body is impermanent...^{}//[similes][craving][rebirth]|#reference#&references&`
3. `^fire blown by the wind (mn-72: aggivacchagotta sutta)^{ajahn pasanno}//[]|#simile#&teachings&`
4. `^a former monk asks ajahn chah about working with dying people to give them the opportunity for wholesome rebirth.^{ajahn pasanno}//[ajahn chah][death]+[teachers][rebirth][fierce/direct teaching]|#story#&stories&`
5. `^i practice dying. the dalai lama^{ajahn pasanno}//[dalai lama][recollection/death]|#indirectquote#&quotes&`

The format of each blob can be informally represented as: `^text^{teachers}[qTags]//[aTags]|#kind#duration#&category&@eventCode@sNN@xNN@`.

`sNN` is the zero-padded session number, so Session 1 is `s01`; `xNN` is the zero-padded excerpt number. `[qTags]` and `@eventCode@sNN@` do not appear in annotations. Text-only searches match text on the left of the `|` separator symbol. To match `kind`, `duration`, `category`, and `eventCode`, the query must include the symbols `#`, `&`, or `@`.

Tags for which this excerpt is featured are marked `+`, e.g. `[death]+`.

Excerpts which are elligible to be featured on the homepage include `#homepage#` immediately after the separator symbol.

Duration is one of the following: `veryshort`, `short`, `medium`, `long`, `verylong`.

Search queries are broken into individual strings separated by spaces. If all search strings can be found within an excerpts' blobs, then the excerpt is considered to be found.

The search engine implements the following wildcard characters:

`_` matches any single character except those with special meaning in the blobs: `^|#&@[]{}<>()`

`*` matches any number of characters except those with special meaning

`$` matches a word boundary

Spaces divide individual search strings except for groups of characters enclosed in double quotes. Characters enclosed in double quotes only match word boundaries, but this can be changed using `*`. For example, `"Thai*"` and `$Thai` are equivalent queries.

Search terms enclosed in backticks are raw regular expressions, e.g. `` `@.*200[0-9]` `` finds all excerpts from events in the decade starting in 2000. [regexr.com](https://regexr.com/) is a good reference and playground for building regular expressions.

With a bit of ingenuity, complex searches can be built up out of simpler components. For example, suppose you want to find all excerpts where someone other than Ajahn Pasanno contributed. This search can be constructed as follows:

1. `!{Ajahn Pasanno}` finds all excerpts with a blob without Ajahn Pasanno as a teacher.

2. But some of these blobs have no teachers at all. Blobs with no teacher contain `{}`, so these can be eliminated by adding a term to the search to get `!{Ajahn Pasanno} !{}`.

3. But we would also like to find excerpts in which both Ajahn Pasanno and another teacher contribute. `"{*}{*}"` finds excerpts that have blobs with at least two teachers. If one of these is Ajahn Pasanno, the other must be someone else. Thus `{Ajahn Pasanno} "{*}{*}"` finds all excerpts with two-teacher blobs in which Ajahn Pasanno contributes.

4. Finally, combining these with the or operator yields the desired result: `|(&(!{Ajahn Pasanno} !{}) &({Ajahn Pasanno} "{*}{*}"))`.

5. You can test this search [here](search:'|(&(!{Ajahn Pasanno} !{})  &({Ajahn Pasanno} "{*}{*}"))'). Try adding @TG to find the six Thanksgiving Retreat exceprts where another teacher contributed.