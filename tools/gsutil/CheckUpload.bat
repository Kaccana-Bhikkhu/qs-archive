Q:
cd \qs-archive

echo "Before first command"

call gsutil -m rsync -r -d -n audio/excerpts gs://apqs_archive/audio/excerpts

echo "Finished first command"

call gsutil -m rsync -r -d -n -x ".*json$" prototype gs://apqs_archive/prototype

echo "Finished second command"