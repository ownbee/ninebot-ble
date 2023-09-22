# Ninebot Scooter BLE Python client

Python client for interfacing with a Ninebot scooter using bluetooth low energy (BLE).

It is primarely using the BLE UART characteristic for communication with the scooter. It is also
using the new encrypted protocol using [miauth](https://github.com/dnandha/miauth) library. Old
scooter firmwares might therefore not work.

The projects primary objective is to support Home Assistant integration but will work for more
use-cases as well.

## Usage

Installation:

```
pip install ninebot-ble
```

A command-line client for testing purposes are shipped:

```
ninebot-ble --help
```

## Troubleshoot

I only have access to a Ninebot F-series scooter, if you have problems with other models, I will
need help with debugging.
