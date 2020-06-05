picomc
====

`picomc` is a cross-platform command-line Minecraft launcher. It supports
all(?) officialy available Minecraft versions, account switching and
multiple separate instances of the game. The on-disk launcher file
structure mimics the vanilla launcher and as such most mod installers
(such as forge, fabric or optifine) should work with picomc just fine,
though you will have to change the installation path.
Don't hesitate to report any problems you run into.

Installation
---

The easiest and most portable way to install picomc is using pip, from the
Python Package Index (PyPI):

```
pip install picomc
```

Depending on your configuration, you may either have to run this command
with elevated privileges (using e.g. `sudo`) or add the `--user` flag like this:

```
pip install --user picomc
```

Usage
---

The quickest way to get started is to run

```
picomc play
```

which, on the first launch, will ask you for your account details,
create an instance named `default` using the latest version of Minecraft
and launch it.

Of course, more advanced features are available. Try running

```
picomc --help
```

and you should be able to figure it out. More detailed documentation
may appear someday in the future.
