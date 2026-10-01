class ProgressCalculator():
    def __init__(self, total):
        self.total_steps = int(total)
        if self.total_steps > 0:
            self.step_percent = 100/self.total_steps
        else:
            self.step_percent = 0
        self.current_step = 1
        self.current_percent = self.step_percent
    
    def get_step_percent(self, step):
        self.current_percent = self.step_percent * step
        return self.d()
    
    def add(self,vreturn=True):
        self.current_step +=1
        self.current_percent += self.step_percent
        #print("Step Percent:", self.step_percent)
        #print("Current Percent:", self.current_percent)
        if vreturn == True:
            return self.d() ## display value
            
    def d(self): ## display value
        if self.current_percent < 100:
            return int(self.current_percent)
        else: 
            return 100