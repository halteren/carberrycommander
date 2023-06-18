# carberrycommander

A smarter way to shutdown the RaspberryPi in your car.

## Installation

Install the files into the folder **/home/pi/carberrycommander**.
Copy <code>env.example</code> to <code>env</code> and edit to your specific situation.

Ensure the required Python packages are installed on the Pi.

```bash
sudo pip3 install -r requirements.txt
```

Copy <code>carberrycommander.service</code> to **/etc/systemd/system**.
Enable and start the service:

```bash
sudo systemctl enable carberrycommander
sudo systemctl start carberrycommander
```

## Settings

* **TIMER1** - The duration in seconds after an IGNITION OFF event untill the Carberry shield starts emitting GOTOSLEEP events.
* **IGNORE_STATIONS** - A comma separated list of MAC address that should be ignored to decide to go to sleep.
* **HOME_COORD** - (Lat,Lon) coordinates of your home address.

## Contributing

Pull requests are welcome. 

## License

[MIT](https://choosealicense.com/licenses/mit/)