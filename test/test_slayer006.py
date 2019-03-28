import sys, os

CURRENT_TEST_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(CURRENT_TEST_DIR + "/../src")

import numpy as np
import matplotlib.pyplot as plt
import torch
from data_reader import SlayerParams
from slayer import spikeLayer
from spikeLoss import spikeLoss

###############################################################################
# testing spike learning ######################################################
net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/snnData/network.yaml")

Ns   = int(net_params['simulation']['tSample'] / net_params['simulation']['Ts'])
Nin  = int(net_params['layer'][0]['dim'])
Nhid = int(net_params['layer'][1]['dim'])
Nout = int(net_params['layer'][2]['dim'])

net_params['training']['error']['type'] = 'NumSpikes'

device = torch.device('cuda')

class Network(torch.nn.Module):
	def __init__(self, net_params, device=device):
		super(Network, self).__init__()
		# initialize slayer
		slayer = spikeLayer(net_params['neuron'], net_params['simulation'], device=device)

		self.slayer = slayer
		# define network functions
		self.spike = slayer.spike()
		self.psp   = slayer.psp()
		self.fc1   = slayer.dense(Nin, Nhid)
		self.fc2   = slayer.dense(Nhid, Nout)
		
	def forward(self, spikeInput):
		spikeLayer1 = self.spike(self.fc1(self.psp(spikeInput)))
		spikeLayer2 = self.spike(self.fc2(self.psp(spikeLayer1)))
		return spikeLayer2
		
snn = Network(net_params)

# load input spikes
spikeAER = np.loadtxt('test_files/snnData/spikeIn.txt')
spikeAER[:,0] /= net_params['simulation']['Ts']
spikeAER[:,1] -= 1
spikeData = np.zeros((Nin, Ns))
for (tID, nID) in np.rint(spikeAER).astype(int):
	if tID < Ns : spikeData[nID, tID] = 1/net_params['simulation']['Ts']
spikeIn = torch.FloatTensor(spikeData.reshape((1, Nin, 1, 1, Ns))).to(device)

# desired class
desiredClass = torch.zeros((1, Nout, 1, 1, 1)).to('cpu')
# desiredClass[0,0,0,0,0] = 1 # commenting this will make the network spike 3 times

# define error module
error = spikeLoss(snn.slayer, net_params['training']['error'])

# define optimizer module
optimizer = torch.optim.Adam(snn.parameters(), lr = 0.01, amsgrad = True)


losslog = list()
spikeRaster = np.empty((0,2))

for epoch in range(500):
	spikeOut = snn.forward(spikeIn)
	spikeTimes = np.argwhere(spikeOut.reshape((Nout, Ns)).cpu().data.numpy())
	# if spikeTimes.size > 0:
	spikeTimes[:,0] += epoch
	spikeRaster = np.append(spikeRaster,spikeTimes, axis=0)
	
	loss = error.numSpikes(spikeOut, desiredClass)
	if epoch%10 == 0:	print('loss in epoch', epoch, ':', loss.cpu().data.numpy() * 10 * 2)
	losslog.append(loss.cpu().data.numpy())
	
	optimizer.zero_grad()
	loss.backward()
	optimizer.step()
	
outputAER  = np.argwhere(spikeOut.reshape((Nout,Ns)).cpu().data.numpy() > 0)

plt.figure(1)
plt.plot(losslog)

plt.figure(2)
plt.plot(spikeRaster[:,1], spikeRaster[:,0], '.')

plt.show()