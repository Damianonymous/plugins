# Changelog

## 2018-08-19
### Changed
- **plugins.fc2**: changed websocket param
- **plugins.showup**: use wss instead of ws
- **plugins.resolve**: iframe regex cleanup
- **plugins.resolve**: changes some log.debug to log.trace
- **plugins.resolve**: Fixed wrong regex for unescape_type iframes
- **plugins.resolve**: playlist_re update for \ before the last "

### Removed
- **plugins.resolve**: removed p.a.c.k.e.r support.
- plugin test files

## 2018-08-14
### Changed
- **plugins.showup**: ws host update

## 2018-08-07
### Changed
- **plugins.resolve**: removed itertags, use re

## 2018-07-12
### Added
- **plugins.rutube**: metadata for the --title command

### Changed
- All Plugins: use self.session.http instead of http

## 2018-07-10
### Added
- README: New Guide
- plugins.myfreecams: support for wzobs servers
- plugins.myfreecams: DASH streams but only for h5video servers
                      and --myfreecams-dash must be used.

### Changed
- plugins.myfreecams: some log error's are now PluginError's,
                      the console output is a bit different,
                      also added more debug messages.

## 2018-07-09
### Added
- **common_packer**: Unpacker for Dean Edward's p.a.c.k.e.r
  The p.a.c.k.e.d feature is experimental and might not work for every packed m3u8 URL.
  It is used with the resolve plugin, but can also be used for other plugins.
- **plugins.resolve**: User input for iframes
  If a website has more than one iframe,
  the user will be asked to choose which iframe should be used.
- **plugins.resolve**: support for unescaped m3u8 URLs

### Changed
- **plugins.resolve**: Added a chat domain for the static blocklist

## 2018-07-07
### Added
- **plugins.resolve**: basic support for plugin.get_title()

### Changed
- **plugins.resolve**: moved self.url into init
- **plugins.resolve**: use res_text as self.html_text

## 2018-07-06
### Added
- **plugins.otr**: New plugin for ОТР

### Changed
- **Streamlink 0.14.2+20.gc394b41** is now required for hlssession.py, resolve.py
- **plugins.resolve**: speedup compare_url_path

## 2018-07-04
### Added
- **plugins.resolve**: New command --resolve-blacklist-filepath

### Changed
- **plugins.resolve**: Block the path end '/novideo.mp4'
- **README** - Linux Guide update
- **README** - Plugin Guide cleanup, `streamlink -h` should be used

## 2018-07-01
### Added
- debug log message for the plugin version
