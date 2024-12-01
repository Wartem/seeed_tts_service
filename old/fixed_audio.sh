#!/bin/bash

# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root or with sudo."
    exit 1
fi

# Create or overwrite /etc/asound.conf with the specified content
cat << EOF > /etc/asound.conf
# The IPC key of dmix or dsnoop plugin must be unique
# If 555555 or 666666 is used by other processes, use another one
# use samplerate to resample as speexdsp resample is bad
defaults.pcm.rate_converter "samplerate"
# The IPC key of dmix or dsnoop plugin must be unique
defaults.pcm.rate_converter "samplerate_best"

pcm.!default {
    type asym
    playback.pcm "playback"
    capture.pcm "capture"
}

pcm.playback {
    type plug
    slave.pcm "dmixed"
}

pcm.capture {
    type plug
    slave.pcm "array"
}

pcm.dmixed {
    type dmix
    slave {
        pcm "hw:0"
        rate 48000
        period_size 1024
        buffer_size 4096
        periods 2
    }
    ipc_key 555555
}

pcm.array {
    type dsnoop
    ipc_key 666666
    ipc_key_add_uid true
    slave {
        pcm "hw:0"
        channels 2
        rate 48000
        period_size 1024
        buffer_size 4096
        periods 2
    }
}

ctl.!default {
    type hw
    card 0
}
EOF

echo "ALSA configuration has been written to /etc/asound.conf"