[Ajahn Pasanno in Thailand, December 2015](photo:LPP with novices Thailand Dec 2015.jpg)

- 1.0: First publicly available prototype; contains all questions from Thanksgiving Retreats 2013-2015 from pre-existing transcriptions; subject tags are based on transcription text rather than audio content.

- 1.9: Index stories, quotes, and readings in addition to questions. Added Spirit Rock daylong events from 2010 and 2011. The tag list has expanded to include tags from many events transcribed on paper that have not yet been entered into the online archive. Almost all documentation still applies to version 1.0.

- 1.91: Added events: DRBU Q&A, The Teaching and the Training, and Living in a Changing Society. Remove unused tags from the tag list (possibly still a few glitches).

- 1.92: Added Teen Weekend 2017. Added teacher pages.

- 1.93: Added Tea Time Q&A and Abhayagiri Kaṭhina 2021. Embed audio players in the page for each excerpt. This allows one to read transcriptions while listening to the talk, but clutters the visual interface.

- 2.0 (May 15, 2023): All pages look much better thanks to css code contributed by Chris Claudius.

- 2.1 Added three Upāsikā Days: Thai Forest Tradition, Mindfulness of Breathing, and Jhāna: A Practical Approach

- 2.1.1 Added three Upāsikā Days: Honoring the Buddha, The Middle Way of Not-self, and Death and Dying. Added the Spirit Rock Daylong about Friendship.

- 2.1.2 Added the 2008 Metta Retreat and the Spirit Rock Daylong Desire or Aspiration. Assigned copyright to Abhayagiri Buddhist Monastery.

- 2.1.3 Added Upāsikā Day: Right Livelihood.

- 2.2 Implemented session excerpts. Added Stanford Communtiy Dhamma Discussion and Upāsikā Day: Buddhist Identity. Added three sessions from Winter Retreat 2014 for testing purposes.

- 2.3 Added Chanting Upāsikā Day and Path of Practice weekend.

- 2.3.1 Added three more Upāsikā Days and BIA New Year, New Life.

- 3.0 Floating media player (Thanks Owen!). Drill-down tag hierarchy. Category subsearch on All Excerpts and tag pages. About pages are rendered from markdown files in documentation/about.

- 3.1 Alphabetical tag listings. List events by series and year. List teachers chronologically and by lineage. Category search on teacher pages. Links between teacher and tag pages. Calming the Busy Mind Upāsikā Day.

- 3.2 Move website to pages directory. Reogranize python and assets files. Reorganize tag hierarchy. Document event series and tags. Render links to tags and events. Fix links to bookmarks from external pages.

- 3.2.1 Add About pages: Overview, Ways to Help, and Licence. Thanksgiving Retreat 2016. Retag Thanksgiving Retreat 2015.

- 3.2.2 Add About pages: What's new? and Contact. Render links to teachers, about pages, images, and the media player. Complex workaround needed to link to non-page items (e.g. images) in Document.RenderDocumenationFiles. Loading images properly in both the static html pages and frame.js will require modifications to frame.js.

- 3.3 Add Glosses column in Tag sheet. Improve alphabetical tag list. Enable tag sorting by date. Events listed in tag pages. Indirect quotes link to teacher. Added Upāsikā Day 2018: The New Ajahn Chah Biography.

- 3.3.1 Apply ID3 tags to excerpt mp3 files.

- 3.3.2 Download icon. Readings can now be annotations. Minor changes to session excerpts. Winter Retreat 2015 partially complete (through Session 13).

- 3.3.3 Download only changed sheets. Word count. Upload to abhayagiri.org. Audio icon on All/searchable pages. Links between about and series pages.

- 3.3.4 Add --mirror option to specify possible sources of audio and reference files. Winter Retreat 2015 through Session 24.

- 3.3.5 Suggested citation footer (needs polishing). Documentation updates.

- 3.4 Add photos to documentation. Much improved citation footer title. Html meta tag keywords. Remove meta robots search engine block. Several layout changes in preparation for Chris Claudius's new style sheet. --linkCheckLevel option.

- 3.4.1 Redirect plain pages to index.html#path. Add links to subsearches in All Excerpts pages. Add subsearch keywords and page descriptions. --urlList option for search engine submissions.

- 3.4.2 Fix back button after following bookmark links. Add many teacher dates. Documentation changes suggested by Ajahn Suhajjo.

- 3.5 Style update by Chris Claudius.

- 3.5.1 Updated license page, teacher ordination dates, and ID3 tags. Version list and License moved to Technical submenu. Remove mistaken robots exclusion tag introduced in Version 3.5.

- 3.5.2 Make no script website (homepage.html) more accessible.

- 3.5.3 (November 2023 Release) Don't preload audio to reduce data usage.

- 3.6 Added Upāsikā Days: On Pilgrimage and Tudong and Developing Skill in Reflective Meditation. Drilldown html files named by tag. Count excerpts referred to by subtags in hierarchical lists. Fix bug that removed "Refraining from:" and other list headings. Fix bug where bookmarks scroll to the wrong place in pages with slow-loading images.

- 3.6.1 Added three Upāsikā Days: Two Kinds of Thought, Practice in a Global Context, and Love, Attachement, and Friendship. Numerical tag page shows canonical numbered lists. Cache checksums of many files and overwrite them only when needed. Fix bug where csv files were downloaded multiple times.

- 3.6.2 Finished Winter Retreat 2015. DownloadFiles.py downloads needed mp3 and pdf files from remote URLs. System of clips and audioSources will allow more flexible audio processing. Fix bug displaying incorrect number of excerpts in event lists. Fix frame.js bug with #noscript links.

- 3.6.3 Add Page Not Found page. Add custom CLIP ID3 tag to excerpt mp3s to describe the audio source. Check if the mp3 CLIP tag matches the excerpt clip. If not, SplitMp3 recreates the mp3 file. Move unneded files to NoUpload directories.

- 3.6.4 Add CheckLinks module. Include only about pages and events in sitemap.xml. New command line options: --args Filename.args includes the arguments in Filename.args in the command line; --no-XXX sets boolean option XXX to False; --multithread allows multithreaded http operations.

- 3.6.5 (December 2023 release) Don't truncate player titles. Fix glitch in multipage excerpt list page menu.

- 3.7 More versatile audio processing framework. Don't split excluded excerpts. Allow overlapping clips. Fix player close timout (contributed by Owen). Don't redirect file:// URLs to index.html# to allow simple local browsing. WR2014 finished.

- 4.0 Search feature. Minor changes to WR2014. ParseCSV option --auditNames.

- 4.0.1 Updated many Thai Ajahns' names and dates with information from Krooba Kai. Teacher attributionName field. WR2014 table of contents. ParseCSV option --dumpCSV.

- 4.0.2 (January 2024 release) About page with search instructions.

- 4.1 (July 2024 release) 2001 Ajahn Chah Conference almost finished. Finalized the license. Allow search engines to index pages (fingers crossed). Apply smart quotes to text. ParseCSV option --pendingMeansYes. Unit tests for search feature. Fix several minor bugs.

- 4.1.1 Removed All/Searchable pages.

- 4.2 Added Upāsikā Day: Can We Function Without Attachement? and Ajahn Pasanno's Q&A sessions from the 25th Anniversary Retreat. Obtained teacher consent for almost all Chah2001 excerpts. Added tag search feature. Updated the tags with changes from Version 9. Alphabetical tag listing improvements. search.js is more readable. Database-related functions moved to Database.py.

- 4.2.1 (August 2024 release) Minor changes to tags and alphabetical tag listings. Minor fixes to search display.

- 5.0 Key topics, featured excerpts, and tag clusters. Edited audio and Alternate audio annotations. toggle-view implemented in Javascript. Rewrite Filter.py to use Filter class instead of functions. Fixed the long-standing scroll bug ([issue #52](https://github.com/Kaccana-Bhikkhu/qs-archive/issues/52)) when pressing back. Allow root index.html to be indexed. Added events: Madision2023, Rishikesh 2023, Podcast 2023. Listened in detail to some excerpts from TG2014 and the first four sessions of TG2015.

- 5.0.1 Events by subject page. Added annotations to TG2015 sessions 5-8.

- 5.0.2 (October 2024 release) Fix Google indexing redirect error for index.html.

- 5.1 (November 2024 release) All subtopics feature at least one excerpt. Annotations can be featured using a Fragment annotation. The first part of an excerpt can be featured using a Main Fragment annotation. Append Audio and Edited Audio annotations. Review Database module estimates the optimal number of featured excerpts. Search for qTags and aTags using '//' as a prefix or suffix. '!' search not operator. Use Javascript to improve the tag drilldown interface. Listened in detail to some excerpts from TG2016.

- 5.2 Home page displays random key excerpts. ExportAudio module copies excerpt audio files to an external directory. Both new features are alpha quality in this version.

- 5.3 (December 2024 release) Search all button. Random excerpt generation moved to search page. Added events: Abhayagiri Anniversaries 2016 (partial), 2021, and 2025; Practice and Study Day 2023. Listened in detail to some excerpts from TG2013. Reviewed and edited audio for many featured excerpts.

- 5.4 (May 2025 release) Added events: Winter Retreat 2005 Ānāpānasati, Winter Retreat 2016 (partial), Awaken to the New Year 2021, Spirit Rock 2023 and 2024 daylongs, a 2025 Wat Pah Nanachat Q&A session, and two online events from 2024. Most tags applied to over 25 excerpts feature at least one excerpt. Mp3 splitting with mp3splt. Fixed Javascript bugs on Firefox and Mac browsers.

- 5.4.1 (May 2025 release #2) Play all featured excerpts on tag and cluster pages. Contributed by Owen.

- 6.0 (June 2025 release) Home page redesigned by Chris Claudius. Floating search bar available from the main menu and by pressing '/' anywhere on a page. SetupFeatured.py manages the daily featured excerpt history database. Improved support for small screens. Dispatch pages explain the features of the archive in detail. Html sitemap. Remove NN_ from the about page filenames. Html redirects from pages which have moved.

- 6.1 (July 2025 release) Add auto complete to floating search bar. Add icons to search results and many other pages. Add more sessions to Winter Retreat 2016. More teachers have given permission for Abhayagiri's 20th anniversary event.

- 6.2 (August 2025 release) Color icons represent each key topic. Can be installed as a progressive web app (but has no offline capability).

- 6.2.1 (August 2025 release 2) Added events at Amaravati: Questions and Answers about Ajahn Chah and What Luang Por Chah Taught. Regular expression searches using `` `regexp` ``. `#homepage` finds excerpts featured on homepage. RemakeFuture and Trim submodules in SetupFeatured.py. Fix pydub compatibility with Python 3.13. Fix bugs in homepage timer.

6.3 (September 2025 release) First 20 sessions of Winter Retreat 2025. Winter Retreat 2016 finished except for 4 sessions. Chithurst 2025 Q&A session. Sutta links go to [SuttaCentral](https://suttacentral.net); links to sutta subsections. Alt-clicking a sutta link goes to [readingfaithfully.org](https://sutta.readingfaithfully.org). --pendingMeansYes option changed to --includePending. PrepareUpload cautions about removed pages.

6.4 (November 2025 release) Winter Retreat 2025 through Session 46. Chithurst Kaṭhina Q&A sessions. Sutta, vinaya, and book reference pages show excerpts that refer to a particular source. Alt-clicking on sutta, vinaya, and book links takes one to the corresponding reference page. Revamped WR2014 and WR2016 table of contents. ID3 "SPLT" key stores json-encoded information about the split and join methods used to make excerpt mp3 files.

6.5 (December 2025 release) Winter Retreat 2013 through session 27. Upāsakā Day: Becoming the Buddha. Display special excerpts on the homepage on significant anniversaries. SetupFeatured minimizes changes to the calendar. Boolean search operations. Sort search results by relevance. Default to Bhante Buddharakkhita's tranlsation of the Dhammapada and John D. Ireland's translation of the Itivuttaka. Display the first few words of Dhammapada verses. Link to SuttaCentral Express when Javascript is off. Pydub join operations use a bitrate matching the source files.