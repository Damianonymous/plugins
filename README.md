# back-to/plugins

[![TravisCI build status][travisci-build-status-badge]][travisci-build-status]

Plugins in this Repository are built for **Streamlink 0.14.2+20.gc394b41**
don't expect them to work with the **stable version** of Streamlink.

Submit Questions and Plugin Issue [here][github-issues].

A lot of website are loading to many unnecessary scripts
which slows the computer for no good reason.

The **main purpose** of these plugins is the ability to watch the Video
in a **Videoplayer** such as VLC or MPV instead of a Webbrower.

### GIT source

- [Github][github]
- [Gitlab][gitlab] (mirror)

# Plugin Matrix

`resolve.py` is the main plugin of this repo, it is a **generic Streamlink Plugin**
which will **try** to find a valid Video URL on every website.

You can get a **guide** of every plugin command with `streamlink -h`.

For the other plugins, just go throw them and see if you need something.

# Guide

### How can I use the Streamlink Development version?

- [Linux][install-linux]
- [Windows][install-windows]

### How can I download these Plugins?

If you are on Linux, the best way is to use `git`

If you are on something else you can just download the [ZIP file][repo-zip]

### How can I use these Plugins?

The best way is to sideload them with Streamlink,
you will have to create a new folder and put them in it.

| Platform          | Location           |
| -------------     | -------------      |
| Unix-like (POSIX) | $XDG_CONFIG_HOME/streamlink/plugins |
| Windows           | %APPDATA%\streamlink\plugins        |

For more details see [here][streamlink-sideloading]

### How can I use these Plugins with Kodi?

[repository.back-to][repository.back-to] must be installed

- open in Kodi **Add-ons / Add-on browser**
- click on **Install from repository**
- click on **back-to repository**
- click on **service**
- click on **LiveProxy**
- click on **Dependencies**
- search for **back-to plugins**
- install it
- done

### Linux Quick Install Guide

you will have to create the default streamlink config folder


```sh
mkdir $HOME/.config/streamlink
```

clone it and make a symbolic link

```sh
git clone https://github.com/back-to/plugins.git
cd plugins
ln -s "$(pwd)/plugins/" "$HOME/.config/streamlink/"
```

you can update the plugins with git in the folder where it was cloned

```sh
git pull origin master
```

you can also put your own custom plugins in the plugins folder,
if they are named `hidden_NAME.py` they won't interfere with the git command.

  [github-issues]: https://github.com/back-to/plugins/issues
  [github]: https://github.com/back-to/plugins
  [gitlab]: https://gitlab.com/back-to/plugins
  [install-linux]: https://streamlink.github.io/latest/install.html#source-code
  [install-windows]: https://bintray.com/streamlink/streamlink-nightly/streamlink/_latestVersion/#files
  [repo-zip]: https://github.com/streamlink/streamlink/archive/master.zip
  [repository.back-to]: https://github.com/back-to/repo/raw/master/repository.back-to/repository.back-to-5.0.0.zip
  [streamlink-sideloading]: https://streamlink.github.io/latest/cli.html#sideloading-plugins
  [travisci-build-status-badge]: https://travis-ci.org/back-to/plugins.svg?branch=master
  [travisci-build-status]: https://travis-ci.org/back-to/plugins
