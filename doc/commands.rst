Command line interface
======================

Some of the functionality in Manwë is provided through a simple command line
interface.

Since the average scientist is too lazy to write complete documentation,
you'll just find a quick dump of the command line help output below.

::

    martijn@hue:~$ manwe -h
    usage: manwe [-h] [--config CONFIG_FILE]

                       {import-sample,activate,sample,add-user,user,data-source,download-data-source}
                       ...

    Manwë command line interface.

    optional arguments:
      -h, --help            show this help message and exit
      --config CONFIG_FILE  path to configuration file to use instead of looking
                            in default locations

    subcommands:
      {import-sample,activate,sample,add-user,user,data-source,download-data-source}
                            subcommand help
        import-sample       import sample data
        activate            activate sample
        sample              show sample details
        add-user            add new API user
        user                show user details
        data-source         show data source details
        download-data-source
                            download data source and write data to standard output
