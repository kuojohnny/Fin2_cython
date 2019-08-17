from sys import argv
import math
import data_structure

file_path = 'trace/'
file_name = 'FAT32.txt'

class Execute():

    operation = {}
    devices = None


    # Configuration
    parity_assignement = 92
    parity_order = 0
    num_block = 1048
    num_page = 256


    mapping_table = None
    stripe_buffer = None


    semi_stripe_table = None
    binded_stripe_table = None

    # PPC
    ppc = None
    max_ppc_size = 16

    replacement = 0

    # result
    # [write_count, parity_count, erase_count]
    result = [0, 0, 0]

    def __init__(self):
        self.devices = []
        self.mapping_table = {}
        self.stripe_buffer = []

        self.semi_stripe_table = {}
        self.binded_stripe_table = {}
        self.ppc = []

        for i in range(5):
            self.devices.append(data_structure.Device(i,
                                                      self.mapping_table,
                                                      self.devices,
                                                      self.semi_stripe_table,
                                                      self.binded_stripe_table,
                                                      self.ppc,
                                                      self.max_ppc_size,
                                                      self.result
                                                      ))

    def read_file(self, file_name):
        with open(file_path+file_name) as f:
            read_data = f.readlines()
        f.closed
        index = 0
        for line in read_data:
            line = line.split()
            lst = [line[0], int(line[1]), int(line[2])]
            self.operation[index] = lst
            index += 1
        print('Read file finished.')

    def execution(self):
        for time in range(1000000):
            for num in range(len(self.operation)):
                if self.operation[num][0].upper() == 'W':
                    self.write(self.operation[num][1], self.operation[num][2])
            print(time)

    def write(self, sector_addr, sector_size):
        num_page = int(math.ceil(sector_size / 32))
        logical_addr = int(math.ceil(sector_addr / 32))

        for n in range(num_page):
            addr = logical_addr + n
            if addr not in self.mapping_table:    # New write
                if addr not in self.stripe_buffer:
                    self.stripe_buffer.append(addr)
                    if len(self.stripe_buffer) == 4:
                        self.stripe_buffer.reverse()
                        parity_device = self.get_parity_device()
                        physical_addr_arr = [0 for i in range(5)]
                        index = len(self.semi_stripe_table)
                        for i in range(5):
                            if i == parity_device:
                                if self.devices[i].is_free() == True:
                                    phy_addr = self.devices[i].new_parity(index)
                                    physical_addr_arr[i] = phy_addr
                                else:
                                    print('Too much valid data')
                                    exit()
                            else:
                                #check free space
                                if self.devices[i].is_free() == True:
                                    phy_addr = self.devices[i].new_write(self.stripe_buffer.pop(), index)
                                    physical_addr_arr[i] = phy_addr
                                else:
                                    print('Too much valid data')
                                    exit()
                        self.stripe_buffer = []

                        # update table
                        self.semi_stripe_table[index] = list(physical_addr_arr)
                        self.binded_stripe_table[index] = list(physical_addr_arr)
            else:   # Update
                physical_addr = self.mapping_table[addr]
                target_device, target_block, target_page = self.physical_to_reallocation(physical_addr)
                index = 0
                new_physical_addr = 0
                if self.devices[target_device].is_free(target_block) == True:
                    new_physical_addr, target_index = self.devices[target_device].update(target_block, target_page)
                    index = target_index
                else:
                    print('Too much valid data')
                    exit()
                self.binded_stripe_table[index][target_device] = new_physical_addr
                # update ppc
                for i in range(5):
                    if self.devices[i].is_parity_page(self.semi_stripe_table[index][i]) == True:
                        if self.semi_stripe_table[index][i] in self.ppc:
                            self.ppc.remove(self.semi_stripe_table[index][i])
                            self.ppc.insert(0, self.semi_stripe_table[index][i])
                        else:
                            if len(self.ppc) >= self.max_ppc_size:
                                self.ppc.insert(0, self.semi_stripe_table[index][i])
                                commit_parity_location = self.ppc.pop()

                                #cmmit
                                current_device, current_block, current_page = self.physical_to_reallocation(commit_parity_location)
                                commit_index = self.devices[current_device].get_index(current_block, current_page)
                                new_parity_location = 0
                                if self.devices[current_device].is_free(current_block) == True:
                                    new_parity_location = self.devices[current_device].update_parity(current_block, current_page)
                                else:
                                    print('Too much valid data')
                                    exit()
                                #invald old semi stirp table
                                for j in range(5):
                                    if self.semi_stripe_table[commit_index][j] != self.binded_stripe_table[commit_index][j]:
                                        self.devices[j].set_invalid(self.semi_stripe_table[commit_index][j])

                                self.binded_stripe_table[commit_index][current_device] = new_parity_location
                                self.semi_stripe_table[commit_index] = list(self.binded_stripe_table[commit_index])
                                for j in range(5):
                                    self.devices[j].set_valid_semi(self.semi_stripe_table[commit_index][j])
                            else:
                                self.ppc.insert(0, self.semi_stripe_table[index][i])
                        break
        
        # Check device wearout
        if self.devices[self.replacement].device_pe_cycle >= 3000:
            self.replace_device()
            print('Device 0:' + str(self.devices[0].device_pe_cycle) + ', Device 1:' + str(self.devices[1].device_pe_cycle) + ', Device 2:' + str(self.devices[2].device_pe_cycle) + ', Device 3:' + str(self.devices[3].device_pe_cycle) + ', Device 4:' + str(self.devices[4].device_pe_cycle))

    def replace_device(self):
        # Write file
        f = open('write count.txt', 'a')
        counts = str(self.result[0])
        for i in range(5):
            counts = counts + ', ' + str(self.devices[i].write_count)
        f.write(counts)
        f.close()

        f = open('parity count.txt', 'a')
        counts = str(self.result[1])
        for i in range(5):
            counts = counts + ', ' + str(self.devices[i].parity_count)
        f.write(counts)
        f.close()

        f = open('erase count.txt', 'a')
        counts = str(self.result[2])
        for i in range(5):
            counts = counts + ', ' + str(self.devices[i].erase_count)
        f.write(counts)
        f.close()

        temp_mapping_table = {}
        temp_device = data_structure.Device(device_number=self.replacement, mapping_table=temp_mapping_table)
        temp_parity = []    # [index, physical address]
        
        num_migrate_page = math.ceil(len(self.semi_stripe_table) * 90 / 100)
        dst = 0
        if self.replacement == 4:
            dst = 0
        else:
            dst = self.replacement + 1

        # Migrate 90% parity
        for i in range(len(self.semi_stripe_table)):
            if num_migrate_page == 0:
                break
            check_physical_addr = self.semi_stripe_table[i][self.replacement]
            if self.devices[self.replacement].is_parity_page(check_physical_addr) == True:
                if self.semi_stripe_table[i][dst] == self.binded_stripe_table[i][dst]:
                    old_device, old_block, old_page = self.physical_to_reallocation(self.semi_stripe_table[i][dst])
                    new_physical_addr = temp_device.migrate(self.devices[old_device].get_state(old_block, old_page), self.devices[old_device].get_logical_addr(old_block, old_page), i)
                    self.devices[old_device].physical_space[old_block][old_page][0] = 2
                    temp_parity.append([i, self.semi_stripe_table[i][self.replacement]])
                    self.semi_stripe_table[i][self.replacement] = new_physical_addr
                    self.binded_stripe_table[i][self.replacement] = new_physical_addr
                else:
                    # migrate semi
                    old_device, old_block, old_page = self.physical_to_reallocation(self.semi_stripe_table[i][dst])
                    new_physical_addr = temp_device.migrate(self.devices[old_device].get_state(old_block, old_page), self.devices[old_device].get_logical_addr(old_block, old_page), i)
                    self.devices[old_device].physical_space[old_block][old_page][0] = 2
                    temp_parity.append([i, self.semi_stripe_table[i][self.replacement]])
                    self.semi_stripe_table[i][self.replacement] = new_physical_addr
                    # migrate binded
                    old_device, old_block, old_page = self.physical_to_reallocation(self.binded_stripe_table[i][dst])
                    new_physical_addr = temp_device.migrate(self.devices[old_device].get_state(old_block, old_page), self.devices[old_device].get_logical_addr(old_block, old_page), i)
                    self.devices[old_device].physical_space[old_block][old_page][0] = 2
                    self.binded_stripe_table[i][self.replacement] = new_physical_addr
                num_migrate_page -= 1    

        # Migrate 90% data
        for lst in temp_parity:
            if self.devices[dst].is_free() == True:
                phy_addr = self.devices[dst].new_parity(lst[0])
                old_device, old_block, old_page = self.physical_to_reallocation(lst[1])
                self.devices[old_device].physical_space[old_block][old_page][0] = 2
                self.semi_stripe_table[lst[0]][dst] = phy_addr
                self.binded_stripe_table[lst[0]][dst] = phy_addr
                if lst[1] in self.ppc:
                    ppc_index = self.ppc.index(lst[1])
                    self.ppc[ppc_index] = phy_addr
            else:
                print('Too much valid data')
                exit()
        
        #Migrate rest of pages
        for i in range(self.num_block):
            for j in range(self.num_page):
                old_data = self.devices[self.replacement].physical_space[i][j]
                if old_data[0] == 1:
                    physical_addr = temp_device.migrate(old_data[0], old_data[1], old_data[2])
                    self.binded_stripe_table[old_data[2]][self.replacement] = physical_addr
                elif old_data[0] == 3:
                    physical_addr = temp_device.migrate(old_data[0], old_data[1], old_data[2])
                    old_physical_addr = (self.replacement * self.num_block * self.num_page) + (i * self.num_page) + j
                    if old_physical_addr in self.ppc:
                        ppc_index = self.ppc.index(old_physical_addr)
                        self.ppc[ppc_index] = physical_addr
                    self.semi_stripe_table[old_data[2]][self.replacement] = physical_addr
                    self.binded_stripe_table[old_data[2]][self.replacement] = physical_addr
                elif old_data[0] == 4:
                    physical_addr = temp_device.migrate(old_data[0], old_data[1], old_data[2])
                    self.semi_stripe_table[old_data[2]][self.replacement] = physical_addr
                    self.binded_stripe_table[old_data[2]][self.replacement] = physical_addr
                elif old_data[0] == 5:
                    physical_addr = temp_device.migrate(old_data[0], old_data[1], old_data[2])
                    self.semi_stripe_table[old_data[2]][self.replacement] = physical_addr

        #Merge mapping table
        for logical in temp_mapping_table:
            self.mapping_table[logical] = temp_mapping_table[logical] 
        
        del self.devices[self.replacement]
        temp_device.devices = self.devices
        temp_device.mapping_table = self.mapping_table
        temp_device.semi_stripe_table = self.semi_stripe_table
        temp_device.binded_stripe_table = self.binded_stripe_table
        temp_device.ppc = self.ppc
        temp_device.max_ppc_size = self.max_ppc_size
        self.devices.insert(self.replacement, temp_device)


        if self.replacement == 4:
            self.replacement = 0
        else:
            self.replacement += 1

    def physical_to_reallocation(self, physical_addr):
        device = int(physical_addr / (self.num_block * self.num_page))
        block = int((physical_addr % (self.num_block * self.num_page)) / self.num_page)
        page = int((physical_addr % (self.num_block * self.num_page)) % self.num_page)
        return device, block, page

    def get_parity_device(self):
        parity_device = 0
        if self.parity_assignement == 100:
            parity_device = 0
        elif self.parity_assignement == 92:
            if self.parity_order < 92:
                parity_device = 0
            elif self.parity_order < 94:
                parity_device = 1
            elif self.parity_order < 96:
                parity_device = 2
            elif self.parity_order < 98:
                parity_device = 3
            else:
                parity_device = 4
            self.parity_order += 1
        elif self.parity_assignement == 80:
            if self.parity_order < 80:
                parity_device = 0
            elif self.parity_order < 85:
                parity_device = 1
            elif self.parity_order < 90:
                parity_device = 2
            elif self.parity_order < 95:
                parity_device = 3
            else:
                parity_device = 4
            self.parity_order += 1
        elif self.parity_assignement == 60:
            if self.parity_order < 60:
                parity_device = 0
            elif self.parity_order < 70:
                parity_device = 1
            elif self.parity_order < 80:
                parity_device = 2
            elif self.parity_order < 95:
                parity_device = 3
            else:
                parity_device = 4
            self.parity_order += 1
        if self.parity_order == 100:
            self.parity_order = 0
        return parity_device

def main():
    ex = Execute()
    ex.read_file(file_name)
    ex.execution()
    print('end')
