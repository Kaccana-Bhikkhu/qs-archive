<!--TITLE:Want to help?-->
<!--HTML <img src="../../pages/images/photos/Abhayagiri 20th Anniversary.jpg" alt="Preparing for Abhayagiri's 20th Anniversary Celebration" class="cover" title="Preparing for Abhayagiri's 20th Anniversary Celebration" align="bottom" width="200" border="0"/> -->
# Want to Help?
If you would like to contribute to the Ajahn Pasanno Question and Story Archive, here are some possibilities.

-----

## Ways Anyone Can Contribute:

### Find stories in Dhamma talks
The APQS Archive indexes stories told in Q&A sessions and Dhamma discussions. Ajahn Pasanno tells many stories during Dhamma talks, but we’re not planning to hunt for them all. If you remember inspiring stories told by or about Ajahn Pasanno contained in recordings on [abhayagiri.org](https://www.abhayagiri.org/talks), please send them to us. If the story isn’t duplicated elsewhere in the archive and seems worthy to be included, we’ll aim to add it to a future version of the Archive.

When you submit stories, please include:

1. The title and date of the Dhamma talk.
2. A link to the talk on [abhayagiri.org](https://www.abhayagiri.org/) or the [Abhayagiri YouTube Channel](https://www.youtube.com/channel/UCFAuQ5fmYYVv5_Dim0EQpVA).
3. The time the story begins in the recording.
4. A suggested title for the story.

For example: “Master Hsu Yun and the Bandits,” 13:49 in the talk “Developing in Virtue” given by Ajahn Pasanno on May 19, 2012.

<!--HTML<audio-chip src="https://www.abhayagiri.org/media/discs/questions/audio/talks/2012-05-19%20Master%20Hsu%20Yun%20and%20the%20Bandits.mp3" title="Master Hsu Yun and the Bandits"><a href="https://www.abhayagiri.org/media/discs/questions/audio/talks/2012-05-19%20Master%20Hsu%20Yun%20and%20the%20Bandits.mp3" download="Master Hsu Yun and the Bandits.mp3">Download audio</a> ()</audio-chip>-->

----

### Point out typos, tagging errors, or audio glitches
There is so much potential material for the Archive that little proofreading has been done after typing in transcriptions. Thus typos are inevitable, and some tags intended for one excerpt might end up on another. There’s no need for the Archive to be as polished as a printed book, and it often quotes imperfectly phrased questions verbatim. Nevertheless, please let me know if you find any glitches.

-----

## Contributions That Require Skill and Commitment:
### Tag and transcribe Thanksgiving Retreat Questions
__Requirements:__ English proficiency, Comfortable using computers (spreadsheet experience a plus), Attended at least one retreat with Ajahn Pasanno

__Time commitment:__ Most likely 15 hours to learn the system and transcribe your first retreat.

The Archive currently contains questions from the 2013-2016 Thanksgiving Retreats transcribed and time-stamped by the monks who produced the CDs issued shortly after these retreats. The questions are taged based on the transcribe questions but not the audio content of Ajahn Pasanno's answers. I’m hoping that volunteers might listen to these questions, add tags based on the answers, and annotate noteworthy stories, references, and quotes.

If there is energy and enthusiasm after these retreats are finished, there are another half-dozen Thanksgiving Retreats that haven’t been transcribed at all.

----

### Help with programming
__Requirements:__ Proficiency with Javascript web programming, python, and/or Google Sheets gs script

__Time commitment:__ Variable, but programming projects always take longer than you think.

There are many ways a skilled and generous programmer could help with the Archive ([github](https://github.com/Kaccana-Bhikkhu/qs-archive)). Here are some ideas, ranked roughly in order of usefulness with the really big project last.

__Fix bugs:__ For the current list, see [About: status](../../pages/about/08_Status.html#known-issues-and-limitations) and [Github issues](https://github.com/Kaccana-Bhikkhu/qs-archive/issues).

__Cross-platform mp3 splitting:__ The project currently uses Windows-only [mp3DirectCut](https://mpesch3.de/) or [mp3splt](https://mp3splt.sourceforge.net/mp3splt_page/about.php) to quickly and losslessly split mp3 files. mp3splt is cross-platform but occasionally sets the length metadata incorrectly when splitting variable-length mp3 files, so it isn't reliable enough for production work. [FFcuesplitter](https://github.com/jeanslack/FFcuesplitter) is a python script that uses ffmpeg to split mp3 files. It is possible that rewriting `Mp3DirectCut.SinglePassSplit` to use FFCuesplitter would make the QSArchive software fully functional on multiple platforms.

__Help deploy the new homepage:__ A generous supporter has designed a new homepage for the Archive. Integrating it with the current website will stretch the limits of Ajahn Kaccāna's knowledge of Javascript. A skilled Javascript programmer might be able to contribute here.

