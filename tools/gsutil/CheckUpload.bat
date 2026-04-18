Q:
cd \qs-archive

echo "Before first command"

call gsutil -m rsync -r -d -n audio/excerpts gs://apqs_archive/audio/excerpts

echo "Finished first command"

call gsutil -m rsync -r -d -n -x ".*json$" pages gs://apqs_archive/pages

echo "Finished second command"