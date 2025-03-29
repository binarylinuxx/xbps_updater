# XBPS UPDATER
Simple GTK UI for update system with XBPS **PACKAGE MANAGER** full python
im pretty lazy for even one command so... My gtk xbps update manager!

> the utility currenly only alpha 
> dont expect to no bugs to be found

# INSTALL
to install:
```
git clone https://github.com/binarylinuxx/xbps_updater/tree/stable
cd xbps_updater/
sudo ./install.sh
```

> note:
> you can use unstable branch but im not recommend
> might be possible many bugs

# LINKS
[INSTALL](https://github.com/binarylinuxx/xbps_updater#install)

[SCREENSHOTS](https://github.com/binarylinuxx/xbps_updater#screens)

[CONFIG](https://github.com/binarylinuxx/xbps_updater#configuration)

[CONFIG(MORE VERBOSED)](https://github.com/binarylinuxx/xbps_updater#auto-check)

# SCREENS
**UPDATE PROCCES:**
![img1](img/update.png)

**UPDATE FINISH:**
![img2](img/final.png)

# **CONFIGURATION:**
![img3](img/config_page.png)

# AUTO CHECK
by default config auto-generated in ~/.config/upd/upd.ini

configure auto check:
```
[Settings]
check_every = day|week|month
check_through = 1 weeks|months|days
last_check = 2025-03-28 22:38:50 #last check time
notify_threshold = 50 #going base warning based on value you set
critical_threshold = 200 #going important warning based on value 
auto_check = True # True disable auto check

[check]
check-every = day|week|month
check_through = 1 2 3 #how much times through one day week do auto check
```

# IN FEATURE
-- create xbps binary package []

-- submit the package to void repos []

-- full rewriten UI []
